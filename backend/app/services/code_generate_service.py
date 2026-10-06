"""
代码生成 Service 层

负责：

1. 应用 & 权限校验

2. 设置 AI 对话记忆（系统 Prompt / 用户消息 / AI 回复）

3. 流式生成 AI 代码（委托给 AICodeGeneratorFacade）
"""
import logging

from backend.app.common.enums import ChatMessageType, CodeFileType
from backend.app.common.exceptions import ErrorCode, BusinessException
from backend.app.models import AppModel
from .ai_common import get_chat_memory_manager
from .ai_common.tools import get_all_tools_name
from .ai_generator_facade import AICodeGeneratorFacade
from .chat_history_service import create_chat_history_svc

logger = logging.getLogger(__name__)


def validate_and_prepare_code_generation_svc(app_id: int, user_id: int, code_gen_type: str):
    """
    校验应用存在性、用户权限

    Args:
        app_id: 应用 ID
        user_id: 当前登录用户 ID
        code_gen_type: 代码生成类型

    Raises:
        BusinessException: 应用不存在 / 无权限

    Returns:
    """
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.APP_NOT_FOUND, "应用不存在")
    if app.user_id != user_id:
        raise BusinessException(ErrorCode.PERMISSION_DENIED, "您没有权限操作该应用")


def build_code_generator_svc(user_message: str, code_gen_type: CodeFileType, app_id: int):
    """
    构建流式代码生成器

    Args:
        user_message: 用户消息（包含 Prompt）
        code_gen_type: 代码生成类型
        app_id: 应用 ID

    Returns:
        流式代码生成器实例
    """
    tools = None
    if code_gen_type == CodeFileType.VUE_PROJECT:
        tools = get_all_tools_name()
    return AICodeGeneratorFacade.generate_code_and_save_file_streaming(
        user_message, code_gen_type, app_id, tools=tools
    )


def persist_chat_after_generation_svc(
    app_id: int,
    user_id: int,
    init_prompt: str,
    chunks: list[tuple[str, dict]],
) -> None:
    """
    AI 代码生成完成后，将用户消息和 AI 回复写入对话历史 + 内存记忆

    Args:
        app_id: 应用 ID
        user_id: 用户 ID
        init_prompt: 用户原始 Prompt
        chunks: 流式生成的 (event, data) 元组列表，每个元组包含事件类型和数据
                事件类型为 message 时，数据为 token 片段，存入 'd' 键对应的 AI 文本回复
                事件类型为 task_start 时，忽略
                事件类型为 task_end 时，存入 'info' 键对应的任务信息
                事件类型为 error 时，存入 'd' 键对应的错误信息
    """
    full_ai_response = ''
    for event, data in chunks:
        if event == 'message':
            full_ai_response += data['d']
        elif event == 'task_end':
            full_ai_response += data['info']
        elif event == 'error':
            full_ai_response += data['d']
    if not full_ai_response:
        return

    try:
        user_record = create_chat_history_svc(
            message=init_prompt,
            message_type=ChatMessageType.USER.value,
            app_id=app_id,
            user_id=user_id,
        )
        ai_record = create_chat_history_svc(
            message=full_ai_response,
            message_type=ChatMessageType.AI.value,
            app_id=app_id,
            user_id=user_id,
        )

        memory_manager = get_chat_memory_manager()
        memory_manager.add_message(
            app_id=int(app_id),
            role=ChatMessageType.USER.value,
            content=user_record.message,
            db_id=user_record.id,
            token_count=user_record.token_count,
        )
        memory_manager.add_message(
            app_id=int(app_id),
            role=ChatMessageType.AI.value,
            content=ai_record.message,
            db_id=ai_record.id,
            token_count=ai_record.token_count,
        )
    except Exception as e:
        logger.warning(f"保存AI对话历史失败: {str(e)}")
