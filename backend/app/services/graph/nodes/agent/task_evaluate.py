"""
任务类型判断 + 提示词增强节点
对应流程图中「判断任务类型与增强提示词Agent」

对话历史来源：ChatMemoryManager（内存缓存 + DB 加载 + Token 裁剪）
而不是 state.messages，因为 state.messages 是 LangGraph 的 MessagesState 中间态。
"""
import logging
from typing import List, Dict

from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.graph.model.task_evaluate_ai_response import TaskEvaluateResult
from backend.app.services.graph.nodes.agent import create_spec_llm_in_graph
from backend.app.services.graph.prompt import TASK_CLASSIFIER_SYSTEM_PROMPT
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


def _build_chat_messages(state: WorkflowState) -> List[Dict[str, str]]:
    """
    构造发给 LLM 的完整消息列表（历史对话 + 当前用户输入）

    使用 ChatMemoryManager 而非 state.messages 的原因：
    - ChatMemoryManager 自动处理 DB 加载、内存缓存、token 裁剪
    - state.messages 是 LangGraph 的 MessagesState 中间态，可能还没同步 DB
    - ChatMemoryManager 是项目统一的对话历史管理入口

    Args:
        state: 当前工作流状态（需要 app_id 和 original_prompt）

    Returns:
        [{'role': '...', 'content': '...'}] 列表，已做 token 裁剪
    """
    app_id = state.get("app_id")
    original_prompt = state.get("original_prompt", "")

    # extra_messages 是本次调用独有的（当前用户输入），ChatMemoryManager 不会写入 session
    # 这样历史对话保持完整，当前输入只用于本次 LLM 调用
    extra_messages: List[Dict[str, str]] = [
        {"role": "user", "content": original_prompt}
    ]

    if app_id:
        # 有 app_id：从 ChatMemoryManager 加载历史 + token 裁剪
        try:
            # TODO 需要注入 flask 上下文，否则无法调用 db 相关操作，开发阶段跳过数据库读写
            chat_messages = get_chat_memory_manager(memory_only=True).get_llm_messages(
                app_id=app_id,
                extra_messages=extra_messages,
            )
            logger.info(
                f"[task_evaluate] 从 ChatMemoryManager 加载历史: "
                f"app_id={app_id}, 最终消息数={len(chat_messages)}"
            )
            return chat_messages
        except Exception as e:
            logger.error(f"[task_evaluate] ChatMemoryManager 加载失败，降级为仅当前输入: {e}")

    # 兜底：没有 app_id 或加载失败时，仅发送当前用户输入
    logger.info("[task_evaluate] 无 app_id，跳过历史加载，仅发送当前输入")
    return extra_messages


def task_evaluate_node(state: WorkflowState) -> dict:
    """
    判断任务类型并增强提示词

    Args:
        state: 当前工作流状态（需要 original_prompt, app_id）

    Returns:
        dict: 要更新到 state 中的字段
            - task_type: chat / new_build / modify
            - enhanced_prompt: 增强后的提示词
            - current_node: 调试标记
    """
    # 1. 构造 LLM 消息（走 ChatMemoryManager）
    chat_messages = _build_chat_messages(state)

    # 2. 创建带结构化输出约束的 LLM 客户端
    llm_client = create_spec_llm_in_graph(
        system_prompt=TASK_CLASSIFIER_SYSTEM_PROMPT,
        response_format=TaskEvaluateResult.get_response_format(),
    )

    # 3. 调用 LLM（chat_structured 自动解析为 Pydantic 对象）
    try:
        result = llm_client.chat_structured(chat_messages, TaskEvaluateResult)
        logger.info(
            f"[task_evaluate] 任务判断完成: task_type={result.task_type}, "
            f"enhanced_prompt_length={len(result.enhanced_prompt)}"
        )
    except Exception as e:
        logger.error(f"[task_evaluate] 调用 LLM 失败: {e}")
        # 降级策略：当成新建站，增强提示词 = 原始输入
        result = TaskEvaluateResult(task_type="new_build", enhanced_prompt=state.get("original_prompt", ""))

    return {
        "task_type": result.task_type,
        "enhanced_prompt": result.enhanced_prompt,
        "current_node": "task_evaluate",
    }


# ==================== 条件边函数 ====================

def route_after_task_evaluate(state: WorkflowState) -> str:
    """
    根据任务类型决定走向
    - chat → 直接结束（在 code_generator 里处理 chat 回复）
    - new_build / modify → 继续素材收集
    """
    task_type = state.get("task_type", "new_build")
    if task_type == "chat":
        return "code_generator"  # chat 类型也走 code_generator，它会输出 markdown 回答
    return "assets_collector"
