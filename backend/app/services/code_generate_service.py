"""
代码生成 Service 层

负责：

1. 应用 & 权限校验

2. 设置 AI 对话记忆（系统 Prompt / 用户消息 / AI 回复）

3. 流式生成 AI 代码（委托给 AICodeGeneratorFacade）
"""
import logging

from backend.app.common.emuns.chat_message_type import ChatMessageType
from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.extensions.db_instance import db
from backend.app.models.app_model import AppModel
from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.ai_generator_facade import AICodeGeneratorFacade
from backend.app.services.chat_history_service import (
    create_chat_history,
    get_system_prompt_by_app_id,
)

logger = logging.getLogger(__name__)


def validate_and_prepare_code_generation(app_id: int, user_id: int, code_gen_type: str) -> AppModel:
    """
    校验应用存在性、用户权限、设置 code_gen_type

    Args:
        app_id: 应用 ID
        user_id: 当前登录用户 ID
        code_gen_type: 代码生成类型

    Raises:
        BusinessException: 应用不存在 / 无权限 / 代码生成类型无效

    Returns:
        校验通过的 AppModel 实例
    """
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.APP_NOT_FOUND, "应用不存在")
    if app.user_id != user_id:
        raise BusinessException(ErrorCode.PERMISSION_DENIED, "您没有权限操作该应用")

    # 保存 code_gen_type 到数据库
    app.code_gen_type = code_gen_type
    db.session.commit()

    # 如果应用还没有系统 Prompt，先插入一条
    if not get_system_prompt_by_app_id(app_id):
        create_chat_history(
            message=CodeFileType.get_system_prompt(code_gen_type),
            message_type=ChatMessageType.SYSTEM.value,
            app_id=app_id,
            user_id=user_id,
        )

    return app


def build_code_generator(user_message: str, code_gen_type: CodeFileType, app_id: int):
    """
    构建流式代码生成器

    Args:
        user_message: 用户消息（包含 Prompt）
        code_gen_type: 代码生成类型
        app_id: 应用 ID

    Returns:
        流式代码生成器实例
    """
    return AICodeGeneratorFacade.generate_code_and_save_file_streaming(
        user_message, code_gen_type, app_id
    )


def persist_chat_after_generation(
    app_id: int,
    user_id: int,
    init_prompt: str,
    chunks: list,
) -> None:
    """
    AI 代码生成完成后，将用户消息和 AI 回复写入对话历史 + 内存记忆

    Args:
        app_id: 应用 ID
        user_id: 用户 ID
        init_prompt: 用户原始 Prompt
        chunks: 流式生成的 token 片段列表（每项格式 {'d': 'token'}）
    """
    full_ai_response = ''.join(
        chunk['d'] for chunk in chunks
        if isinstance(chunk, dict) and 'd' in chunk
    )
    if not full_ai_response:
        return

    try:
        user_record = create_chat_history(
            message=init_prompt,
            message_type=ChatMessageType.USER.value,
            app_id=app_id,
            user_id=user_id,
        )
        ai_record = create_chat_history(
            message=full_ai_response,
            message_type=ChatMessageType.AI.value,
            app_id=app_id,
            user_id=user_id,
        )

        memory_manager = get_chat_memory_manager()
        memory_manager.add_message(
            app_id=app_id,
            role=ChatMessageType.USER.value,
            content=user_record.message,
            db_id=user_record.id,
            token_count=user_record.token_count,
        )
        memory_manager.add_message(
            app_id=app_id,
            role=ChatMessageType.AI.value,
            content=ai_record.message,
            db_id=ai_record.id,
            token_count=ai_record.token_count,
        )
    except Exception as e:
        logger.warning(f"保存AI对话历史失败: {str(e)}")