"""
对话历史保存节点
对应流程图的最后一步（chat 类型和 new_build/modify 的汇聚点）

保存规则（由用户明确约定）：
┌─────────────────────┬─────────────────────────────────────────────┐
│ 任务类型            │ 保存行为                                    │
├─────────────────────┼─────────────────────────────────────────────┤
│ chat（直接回答）     │ ✅ 保存 user:original_prompt                │
│                     │ ✅ 保存 ai:generate_output（markdown 回答）  │
├─────────────────────┼─────────────────────────────────────────────┤
│ new_build/modify    │ ✅ 保存 user:original_prompt                │
│ qa_pass=True        │ ✅ 保存 ai:generate_output（构建摘要）       │
├─────────────────────┼─────────────────────────────────────────────┤
│ new_build/modify    │ ✅ 保存 user + ai（重试用尽，存最终结果）    │
│ qa_pass=False 且    │                                             │
│ retry>=3            │                                             │
├─────────────────────┼─────────────────────────────────────────────┤
│ new_build/modify    │ ❌ 不保存（审查未通过，继续重试）             │
│ qa_pass=False 且    │                                             │
│ retry<3             │                                             │
└─────────────────────┴─────────────────────────────────────────────┘

持久化流程：

1. 先写 PostgreSQL（chat_history_service.create_chat_history）→ 拿到 db_id

2. 再写内存缓存（ChatMemoryManager.add_message）→ 带上 db_id 回填

这样 ChatMemoryManager 下次从 DB reload 时 id 一致，不会出现重复。
"""
import logging

from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

# code_reviewer 的最大重试次数（和 review 节点保持一致）
MAX_RETRY = 3


def _should_save(state: WorkflowState) -> bool:
    """
    判断当前轮次是否应该保存对话历史

    Returns:
        True → 保存 user + ai 消息
        False → 跳过（审查未通过、重试中）
    """
    task_type = state.get("task_type", "new_build")

    # chat 类型：直接回复，总是保存
    if task_type == "chat":
        return True

    # new_build / modify：只在审查通过或重试用尽时保存
    qa_pass = state.get("qa_pass", False)
    retry_count = state.get("retry_count", 0)

    if qa_pass or retry_count >= MAX_RETRY:
        return True

    # 审查未通过且还有重试次数 → 不保存
    logger.info(
        f"[chat_history_save] 审查未通过 (qa_pass={qa_pass}, retry={retry_count}/{MAX_RETRY})，"
        f"跳过本轮保存"
    )
    return False


def chat_history_save(state: WorkflowState) -> dict:
    """
    对话历史保存节点主函数

    Args:
        state: 当前工作流状态（需要 app_id, user_id, original_prompt, generate_output 等）

    Returns:
        dict: 当前节点标记（不更新业务字段）
    """
    app_id = state.get("app_id")
    user_id = state.get("user_id")
    original_prompt = state.get("original_prompt", "")
    ai_response_message = state.get("ai_response_message", "")

    # 1. 是否需要保存？
    if not _should_save(state):
        return {"current_node": "chat_history_save"}

    # 2. 参数校验
    if not app_id or not user_id:
        logger.warning(
            f"[chat_history_save] 缺少 app_id={app_id} 或 user_id={user_id}，跳过保存"
        )
        return {
            "current_node": "chat_history_save",
            "error_info": "缺少 app_id 或 user_id",
        }

    if not original_prompt and not ai_response_message:
        logger.warning("[chat_history_save] user 和 ai 消息都为空，跳过保存")
        return {"current_node": "chat_history_save"}

    # 3. 先写 DB（拿到 db_id），再写内存缓存 TODO 开发测试环境使用memory_only跳过数据库读写
    memory_manager = get_chat_memory_manager(memory_only=True)

    # --- user 消息 ---
    user_db_id = None
    if original_prompt:
        # TODO 开发测试阶段，跳过数据库读写
        # try:
        #     user_record = create_chat_history(
        #         message=original_prompt,
        #         message_type=ChatMessageType.USER.value,  # "user"
        #         app_id=app_id,
        #         user_id=user_id,
        #     )
        #     user_db_id = user_record.id
        #     logger.info(f"[chat_history_save] user 消息已入库: id={user_db_id}")
        # except Exception as e:
        #     logger.error(f"[chat_history_save] user 消息入库失败: {e}")

        # 写内存缓存（带上 db_id）
        try:
            memory_manager.add_message(
                app_id=app_id,
                role="user",
                content=original_prompt,
                db_id=user_db_id,
            )
        except Exception as e:
            logger.error(f"[chat_history_save] user 消息写入内存缓存失败: {e}")

    # --- ai 消息 ---
    ai_db_id = None
    if ai_response_message:
        # TODO 开发测试阶段，跳过数据库读写
        # try:
        #     ai_record = create_chat_history(
        #         message=ai_message,
        #         message_type=ChatMessageType.AI.value,  # "assistant"
        #         app_id=app_id,
        #         user_id=user_id,
        #     )
        #     ai_db_id = ai_record.id
        #     logger.info(f"[chat_history_save] ai 消息已入库: id={ai_db_id}, length={len(ai_message)}")
        # except Exception as e:
        #     logger.error(f"[chat_history_save] ai 消息入库失败: {e}")

        # 写内存缓存
        try:
            memory_manager.add_message(
                app_id=app_id,
                role="assistant",
                content=ai_response_message,
                db_id=ai_db_id,
            )
        except Exception as e:
            logger.error(f"[chat_history_save] ai 消息写入内存缓存失败: {e}")

    return {"current_node": "chat_history_save"}
