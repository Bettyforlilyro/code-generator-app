"""
代码生成节点（网页生成 Agent）
对应流程图中「网页生成Agent」+「生成或增量修改当前项目代码（有记忆）」

三种场景：
1. task_type == "chat"       → 直接回答用户问题（markdown 文本）
2. code_gen_type == HTML/MULTI_FILE → 结构化输出单文件/多文件代码
3. code_gen_type == VUE_PROJECT     → 带文件工具的 Agent，多轮迭代生成工程
"""
import logging
from typing import List

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.config import get_stream_writer

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.ai_common.tools import tools_factory_with_context
from backend.app.services.ai_generator_facade import processed_chunk
from backend.app.services.graph.model.image_resource import ImageResource
from backend.app.services.graph.nodes.agent import create_spec_llm_in_graph
from backend.app.services.graph.prompt import (
    ENHANCED_PROMPT_TEMPLATE,
    ENHANCED_PROMPT_MODIFY_TEMPLATE,
)
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


def _format_material_info(image_list: List[ImageResource]) -> str:
    """把图片素材列表格式化为 LLM 可读的文本"""
    if not image_list:
        return "无"

    grouped = {}
    for img in image_list:
        cat = img.category.value
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(img)

    lines = []
    type_names = {
        "content": "内容图片",
        "illustration": "插画图片",
        "architecture": "架构图",
        "logo": "Logo 图片",
    }
    for cat, imgs in grouped.items():
        cat_name = type_names.get(cat, cat)
        for img in imgs:
            lines.append(f"  [{cat_name}] {img.description or cat}。图片直链URL: {img.image_url}")

    return "\n".join(lines)


def _build_user_prompt(state: WorkflowState) -> str:
    """
    根据任务类型构建最终发给代码生成 LLM 的用户 prompt
    - new_build: ENHANCED_PROMPT_TEMPLATE
    - modify:    ENHANCED_PROMPT_MODIFY_TEMPLATE
    - chat:      原始增强提示词（保持原样）
    """
    task_type = state.get("task_type", "new_build")
    enhanced_prompt = state.get("enhanced_prompt", "")
    original_prompt = state.get("original_prompt", "")
    image_list = state.get("image_list", [])

    if task_type == "chat":
        # chat 场景直接用原始提问
        return original_prompt

    material_info = _format_material_info(image_list)

    if task_type == "modify":
        return ENHANCED_PROMPT_MODIFY_TEMPLATE.format(
            user_prompt=enhanced_prompt,
            material_info=material_info,
        )
    else:
        # new_build
        return ENHANCED_PROMPT_TEMPLATE.format(
            user_prompt=enhanced_prompt,
            material_info=material_info,
        )


def _build_chat_messages(state: WorkflowState) -> list:
    """
    组装发给代码生成 LLM 的完整消息列表

    ========== 首轮 vs 重试场景 ==========
    - 首轮（retry_count==0 或 无 qa_feedback）：
        extra_messages = [{"role": "user", "content": _build_user_prompt(state)}]
        走 ChatMemoryManager 加载 DB 历史（审查没通过不存，所以首轮一定能读到）

    - 重试（retry_count>0 且有 qa_feedback 且非 chat）：
        直接用 state.messages —— LangGraph add_messages reducer 已经归并了
        上一轮 code_generator return 的 [HumanMessage, AIMessage(full_response)]
        再追加一条 HumanMessage 注入 QA 反馈，让 LLM 看到完整多轮上下文
        绕过 ChatMemoryManager（它从 DB 加载，审查未通过的记录不存）
    ======================================
    """
    app_id = state.get("app_id")
    user_prompt = _build_user_prompt(state)
    task_type = state.get("task_type", "new_build")
    retry_count = state.get("retry_count", 0)
    qa_feedback = state.get("qa_feedback")

    # ========== 关键分支：首轮 vs 重试 ==========
    if task_type != "chat" and retry_count > 0 and qa_feedback:
        # ✅ 重试场景：state.messages 已由 reducer 归并上一轮对话
        # state.messages = [HumanMessage(user_prompt), AIMessage(full_response)]
        # 再追加一条 HumanMessage 注入 QA 反馈
        prev_messages = state.get("messages", [])
        qa_injection = HumanMessage(
            content=(
                f"【代码质量审查专家的反馈意见 —— 请针对性修复以下问题】\n"
                f"{qa_feedback}\n\n"
                f"请重新修改代码，逐一修复以上问题。"
            )
        )
        messages_for_llm = list(prev_messages) + [qa_injection]
        logger.info(
            f"[code_generator] 重试: retry_count={retry_count}, "
            f"已有 state.messages={len(prev_messages)}条, qa_feedback_len={len(qa_feedback)}"
        )
        return messages_for_llm

    # ========== 首轮 / chat 场景 ==========
    extra_messages = [{"role": "user", "content": user_prompt}]

    if app_id:
        try:
            # TODO 需要注入 flask 上下文，否则无法调用 db 相关操作，开发阶段跳过数据库读写（memory_only=True）
            chat_messages = get_chat_memory_manager(memory_only=True).get_llm_messages(
                app_id=app_id,
                extra_messages=extra_messages,
            )
            logger.info(
                f"[code_generator] 从 ChatMemoryManager 加载历史: "
                f"app_id={app_id}, 最终消息数={len(chat_messages)}"
            )
            return chat_messages
        except Exception as e:
            logger.error(f"[code_generator] ChatMemoryManager 加载失败，降级为仅当前输入: {e}")

    # 兜底：没有 app_id 或加载失败
    logger.info("[code_generator] 无 app_id，跳过历史加载")
    return extra_messages


def code_generator_node(state: WorkflowState):
    """
    代码生成节点 —— 普通同步函数 + get_stream_writer 流式方案

    ┌──────────────────────────────────────────────────────────┐
    │ 阶段 1：writer() 吐事件                                    │
    │   chat_stream 每个 chunk → processed_chunk → writer()     │
    │   这些事件立刻进入 stream_mode="custom"，前端实时收到      │
    ├──────────────────────────────────────────────────────────┤
    │ 阶段 2：return dict 合并 state                            │
    │   只有 return 时 LangGraph 才把 dict 合并进全局 state      │
    │   这时候条件边（route_after_code_generator）才会被触发     │
    └──────────────────────────────────────────────────────────┘
    """
    writer = get_stream_writer()

    task_type = state.get("task_type", "new_build")
    code_gen_type = state.get("code_gen_type", CodeFileType.HTML.value)
    messages = _build_chat_messages(state)
    full_response = ""
    tool_context = None
    if task_type == "chat":
        llm_client = create_spec_llm_in_graph(system_prompt="")
    elif task_type == "new_build" and code_gen_type == CodeFileType.VUE_PROJECT.value:
        llm_client = create_spec_llm_in_graph(
            system_prompt="",
            tools=tools_factory_with_context(),
            timeout=1200,
        )
        tool_context = {"app_id": state.get("app_id")}
    else:       # modify 以及 HTML / MULTI_FILE 的 new_build
        llm_client = create_spec_llm_in_graph(system_prompt="", timeout=600)

    try:
        for chunk in llm_client.chat_stream(messages, tool_context=tool_context):
            full_response += chunk.content or ""
            # ✅ 直接用 processed_chunk 转前端约定格式，writer 立刻推出去
            event_type, data = processed_chunk(chunk)
            writer({"event_type": event_type, "data": data})

        if task_type != "chat":
            result = CodeFileType.get_cls_type(code_gen_type).parse_response_from_llm(full_response)
            logger.info(f"[code_generator] 生成完成...")
        else:
            result = full_response

        user_prompt = _build_user_prompt(state)
        return {
            "current_node": "code_generator",
            "generate_output": result,
            "ai_response_message": full_response,
            "messages": [
                HumanMessage(content=user_prompt),
                AIMessage(content=full_response),
            ],
        }
    except Exception as e:
        logger.error(f"[code_generator] 流式生成失败: {e}")
        # 给前端也发一条 error 事件（让用户知道失败了）
        from backend.app.services.ai_common.advisor import StreamChunk
        err_event_type, err_data = processed_chunk(StreamChunk(
            content=f"生成失败：{e}",
            chunk_type=StreamChunk.TYPE_ERROR,
        ))
        writer({"event_type": err_event_type, "data": err_data})
        return {
            "current_node": "code_generator",
            "error_info": f"生成失败：{e}",
            "generate_output": "代码生成失败，请检查网络问题或者API-KEY是否正确。",
        }


# ==================== 条件边函数 ====================

def route_after_code_generator(state: WorkflowState) -> str:
    """
    代码生成后的条件分支
    - chat 类型 → chat_history_save（保存对话历史后结束）
    - new_build/modify → code_reviewer（审查代码）
    """
    task_type = state.get("task_type", "new_build")
    if task_type == "chat":
        return "chat_history_save"
    return "code_reviewer"
