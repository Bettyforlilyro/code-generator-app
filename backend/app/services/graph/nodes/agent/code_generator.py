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

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.ai_common.prompts import CODE_GENERATE_VUE_PROJECT_SYSTEM_PROMPT
from backend.app.services.ai_common.tools import tools_factory_with_context
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

    统一用 ChatMemoryManager 加载历史（自动 DB 加载 + 内存缓存 + token 裁剪），
    extra_messages 只用于本次 LLM 调用，不会写入 session。
    """
    app_id = state.get("app_id")
    user_prompt = _build_user_prompt(state)

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


def _extract_ai_response_message(
    response: str,
    task_type: str,
    code_gen_type: CodeFileType,
) -> str:
    """
    从 llm_client.chat() 的完整响应中，提取给前端展示的纯文本 ai_response_message
    Args:
        response: llm_client.chat() 的完整响应
        task_type: 任务类型（chat / new_build / modify）
        code_gen_type: 代码生成类型（HTML / MULTI_FILE / VUE_PROJECT）
    Returns:
        ai_response_message: 给前端展示的纯文本 ai_response_message（同时也保存到数据库对话历史表）
    """
    # 1. chat 类型直接返回（markdown 回答本身就是给用户看的）
    if task_type == "chat":
        return str(response) if response else ""

    # TODO 其他 task 类型的处理，分 modify / new_build 分支
    if task_type == "modify":
        return ""
    else:
        logger.warning(f"[_extract_ai_response_message] 未知类型: {type(response)}")
        return ""


def _chat_answer(state: WorkflowState) -> dict:
    """
    chat 类型专门分支：直接回答用户问题（markdown 文本），不解析代码

    和 new_build/modify 的区别：
    - 不走 ChatCodeResult 结构化解析
    - generate_output = ai_response_message = markdown 回答
    - 直接路由到 chat_history_save → END
    """
    messages = _build_chat_messages(state)
    # chat 类型不需要 system prompt 里的代码生成约束，直接回答
    llm_client = create_spec_llm_in_graph(system_prompt="")

    try:
        response = llm_client.chat(messages)
        generate_output = response  # str
        ai_response_message = response  # chat 类型两者相等

        user_prompt = state.get("original_prompt", "")
        return {
            "current_node": "code_generator",
            "generate_output": generate_output,
            "ai_response_message": ai_response_message,
            "messages": [
                HumanMessage(content=user_prompt),
                AIMessage(content=response),
            ],
        }
    except Exception as e:
        logger.error(f"[code_generator] chat 回复失败: {e}")
        error_msg = f"抱歉，回答你的问题时出错了：{e}"
        return {
            "current_node": "code_generator",
            "error_info": str(e),
            "generate_output": error_msg,
            "ai_response_message": error_msg,
        }


def _generate_vue_project(state: WorkflowState) -> dict:
    """
    VUE_PROJECT 任务：Agent 模式 + 文件工具
    
    Vue 项目涉及多文件写入，需要 Agent 通过工具逐步创建项目结构。
    """
    # Vue 项目需要绑定文件操作工具
    llm_client = create_spec_llm_in_graph(
        system_prompt=CODE_GENERATE_VUE_PROJECT_SYSTEM_PROMPT,
        tools=tools_factory_with_context(),
    )

    messages = _build_chat_messages(state)

    try:
        tool_context = {
            "app_id": state.get("app_id"),
        }
        response = llm_client.chat(messages, tool_context=tool_context)
        result = CodeFileType.get_cls_type(CodeFileType.VUE_PROJECT.value).parse_response_from_llm(response)
        logger.info(f"[code_generator] VUE_PROJECT 生成完成...")
        ai_response_message = _extract_ai_response_message(response, state.get("task_type", "new_build"), CodeFileType.VUE_PROJECT.value)

        # 本轮交互写入 state.messages，供 reviewer 等节点查看
        user_prompt = _build_user_prompt(state)
        return {
            "current_node": "code_generator",
            "generate_output": result,
            "ai_response_message": ai_response_message,
            "messages": [
                HumanMessage(content=user_prompt),
                AIMessage(content=response),
            ],
        }
    except Exception as e:
        logger.error(f"[code_generator] VUE_PROJECT 生成失败: {e}")
        error_msg = f"Vue 项目生成失败：{e}"
        return {
            "current_node": "code_generator",
            "error_info": error_msg,
            "generate_output": error_msg,
            "ai_response_message": error_msg,
        }


def code_generator_node(state: WorkflowState) -> dict:
    """
    代码生成节点主函数

    三种场景分支（**task_type 优先于 code_gen_type 判断**）：
    ┌─────────────┬──────────────────┬──────────────────────────────────┐
    │ task_type   │ code_gen_type    │ 走哪个内部函数                    │
    ├─────────────┼──────────────────┼──────────────────────────────────┤
    │ chat        │ 任意（忽略）     │ _chat_answer（直接 markdown 回答）│
    │ new_build / │ VUE_PROJECT      │ _generate_vue_project（Agent）   │
    │ modify      │ HTML / MULTI_FILE│ 主流程（结构化解析）              │
    └─────────────┴──────────────────┴──────────────────────────────────┘

    输出字段：
    - generate_output: BaseCodeResult（结构化）或 str（失败/chat）
    - ai_response_message: str（前端展示 + 对话历史持久化）
    - messages: [HumanMessage, AIMessage]（本轮交互，写入 state.messages）
    """
    task_type = state.get("task_type", "new_build")
    code_gen_type = state.get("code_gen_type", CodeFileType.HTML.value)

    # ① chat 类型：直接回答，不走代码生成
    if task_type == "chat":
        return _chat_answer(state)

    # ② VUE_PROJECT：Agent 模式
    if code_gen_type == CodeFileType.VUE_PROJECT.value:
        return _generate_vue_project(state)

    # ③ HTML / MULTI_FILE：结构化解析
    try:
        messages = _build_chat_messages(state)
        llm_client = create_spec_llm_in_graph(system_prompt="", timeout=600)
        response = llm_client.chat(messages)

        result = CodeFileType.get_cls_type(code_gen_type).parse_response_from_llm(response)
        logger.info(f"[code_generator] 生成完成...")

        ai_response_message = _extract_ai_response_message(response, task_type, code_gen_type)

        # 本轮交互写入 state.messages
        user_prompt = _build_user_prompt(state)
        return {
            "current_node": "code_generator",
            "generate_output": result,
            "ai_response_message": ai_response_message,
            "messages": [
                HumanMessage(content=user_prompt),
                AIMessage(content=response),
            ],
        }
    except Exception as e:
        logger.error(f"[code_generator] 生成失败: {e}")
        error_msg = f"代码生成失败：{e}"
        return {
            "current_node": "code_generator",
            "error_info": error_msg,
            "generate_output": error_msg,
            "ai_response_message": error_msg,
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
