"""
对话历史 Service 层

集中封装 ChatHistory 模型的所有数据库操作，供上层业务代码调用。
"""
from datetime import datetime
from typing import Optional

from backend.app.common.emuns.chat_message_type import ChatMessageType
from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.exceptions.exception_handlers import logger
from backend.app.extensions.db_instance import db
from backend.app.models.app_model import AppModel
from backend.app.models.chat_history_model import ChatHistory
from backend.app.models.user import User


# ==================== Create ====================

def create_chat_history(
    message: str,
    message_type: str,
    app_id: int,
    user_id: int,
) -> ChatHistory:
    """
    创建一条对话历史记录

    Args:
        message: 消息内容（必填）
        message_type: 消息类型，可选值：user / ai（必填）
        app_id: 关联的应用 ID（必填）
        user_id: 创建用户 ID（必填）

    Returns:
        创建成功的 ChatHistory 模型对象

    Raises:
        BusinessException: 参数校验失败时抛出
    """
    # 参数校验
    if not message or not message.strip():
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "消息内容不能为空")
    if not message_type:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "消息类型不能为空")
    if not app_id:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "应用 ID不能为空")
    if not user_id:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "用户 ID不能为空")
    if not ChatMessageType.is_valid_message_type(message_type):
        raise BusinessException(
            ErrorCode.INVALID_PARAMETER,
            f"消息类型无效，可选值：{ChatMessageType.get_all_message_types()}"
        )

    try:
        record = ChatHistory(
            message=message.strip(),
            message_type=message_type,
            app_id=app_id,
            user_id=user_id,
        )
        db.session.add(record)
        db.session.commit()
        return record
    except BusinessException:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise BusinessException(ErrorCode.DATABASE_ERROR, f"创建对话记录失败: {str(e)}")


def batch_create_chat_history(messages: list) -> list:
    """
    批量创建对话历史记录

    Args:
        messages: 消息列表，每个元素为 dict，需包含：message, message_type, app_id, user_id

    Returns:
        创建成功的 ChatHistory 模型对象列表

    Raises:
        BusinessException: 参数校验失败时抛出
    """
    if not messages:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "消息列表不能为空")

    records = []
    try:
        for item in messages:
            message = item.get('message')
            message_type = item.get('message_type')
            app_id = item.get('app_id')
            user_id = item.get('user_id')
            record = create_chat_history(
                message=message,
                message_type=message_type,
                app_id=app_id,
                user_id=user_id,
            )
            records.append(record)
        return records
    except BusinessException:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise BusinessException(ErrorCode.DATABASE_ERROR, f"批量创建对话记录失败: {str(e)}")


# ==================== Read ====================

def get_chat_history_by_id(chat_id: int) -> ChatHistory:
    """
    根据 ID 查询单条对话记录

    Args:
        chat_id: 对话记录 ID

    Returns:
        ChatHistory 模型对象

    Raises:
        BusinessException: 记录不存在时抛出
    """
    record = ChatHistory.query.filter_by(id=chat_id, is_delete=0).first()
    if not record:
        raise BusinessException(ErrorCode.RESOURCE_NOT_FOUND, f"对话记录不存在: id={chat_id}")
    return record


def delete_chat_history_by_app_id(app_id: int) -> bool:
    """
    根据应用 ID 删除所有对话历史记录

    Args:
        app_id: 应用 ID

    Returns:
        是否删除成功

    Raises:
        BusinessException: 参数校验失败时抛出
    """
    if not app_id:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "应用 ID不能为空")
    try:
        ChatHistory.query.filter_by(app_id=app_id, is_delete=0).update({'is_delete': 1})
        db.session.commit()
        return True
    except BusinessException:
        db.session.rollback()
        # 记录日志但是不抛出异常
        logger.error(f"删除应用 ID 为 {app_id} 的所有对话记录失败.")
    except Exception as e:
        db.session.rollback()
        raise BusinessException(ErrorCode.DATABASE_ERROR, f"删除对话记录失败: {str(e)}")


def delete_chat_history_by_user_id(user_id: int) -> bool:
    """
    根据用户 ID 删除所有对话历史记录

    Args:
        user_id: 用户 ID

    Returns:
        是否删除成功

    Raises:
        BusinessException: 参数校验失败时抛出
    """
    if not user_id:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "用户 ID不能为空")
    try:
        ChatHistory.query.filter_by(user_id=user_id, is_delete=0).update({'is_delete': 1})
        db.session.commit()
        return True
    except BusinessException:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise BusinessException(ErrorCode.DATABASE_ERROR, f"删除对话记录失败: {str(e)}")


def list_chat_history(
    page: int = 1,
    per_page: int = 10,
    app_id: Optional[int] = None,
    message_type: Optional[str] = None,
    sort_order: str = 'asc',
    last_create_time: Optional[datetime] = None,
    include_system: bool = False,
) -> dict:
    """
    分页查询对话历史列表，只能按照时间排序，默认按时间从早到晚排序

    Args:
        page: 页码，默认 1
        per_page: 每页数量，默认 10
        app_id: 按应用 ID 过滤（可选）
        message_type: 按消息类型过滤（可选），可选值：user / ai，若不选，默认查询所有消息类型"ALL"
        sort_order: 排序方向，asc-正序（时间从早到晚），desc-倒序（时间从晚到早），默认 asc
        last_create_time: 最后创建时间，若不选，默认查询所有记录
        include_system: 是否包含系统消息，默认 False

    Returns:
        分页结果字典，包含 chat_records / total / page / per_page / total_pages / has_next / has_prev

    Raises:
        BusinessException: 参数校验失败时抛出
    """
    # 构建查询
    query = ChatHistory.query.filter_by(is_delete=0)

    if app_id is not None:
        query = query.filter(ChatHistory.app_id == app_id)
    if message_type is not None and message_type != "ALL":
        query = query.filter(ChatHistory.message_type == message_type)

    # 按创建时间排序
    if last_create_time is not None:
        query = query.filter(ChatHistory.create_time > last_create_time)

    sort_column = ChatHistory.create_time
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    if not include_system:
        query = query.filter(ChatHistory.message_type != ChatMessageType.SYSTEM.value)

    # 执行分页查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'chat_records': [r.to_dict() for r in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'total_pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    }


# ==================== Update ====================

def update_chat_history(
    chat_id: int,
    message: Optional[str] = None,
    message_type: Optional[str] = None,
) -> ChatHistory:
    """
    更新对话记录（仅更新传入的非空字段）

    Args:
        chat_id: 对话记录 ID
        message: 新的消息内容（可选）
        message_type: 新的消息类型（可选）

    Returns:
        更新后的 ChatHistory 模型对象

    Raises:
        BusinessException: 记录不存在或参数校验失败时抛出
    """
    record = get_chat_history_by_id(chat_id)

    is_updated = False

    if message is not None:
        if not message.strip():
            raise BusinessException(ErrorCode.INVALID_PARAMETER, "消息内容不能为空")
        record.message = message.strip()
        is_updated = True

    if message_type is not None:
        if not ChatMessageType.is_valid_message_type(message_type):
            raise BusinessException(
                ErrorCode.INVALID_PARAMETER,
                f"消息类型无效，可选值：{ChatMessageType.get_all_message_types()}"
            )
        record.message_type = message_type
        is_updated = True

    if is_updated:
        record.update_time = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise BusinessException(ErrorCode.DATABASE_ERROR, f"更新对话记录失败: {str(e)}")

    return record


# ==================== Delete ====================

def delete_chat_history(chat_id: int) -> None:
    """
    软删除一条对话记录

    Args:
        chat_id: 对话记录 ID

    Raises:
        BusinessException: 记录不存在时抛出
    """
    record = get_chat_history_by_id(chat_id)
    record.is_delete = 1
    record.update_time = datetime.utcnow()
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise BusinessException(ErrorCode.DATABASE_ERROR, f"删除对话记录失败: {str(e)}")


def batch_delete_chat_history(
    app_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> int:
    """
    按条件批量软删除对话记录

    至少需要传入 app_id 或 user_id 其中一个作为删除条件，防止误删全部数据。

    Args:
        app_id: 按应用 ID 删除（可选）
        user_id: 按用户 ID 删除（可选）

    Returns:
        实际删除的记录数量

    Raises:
        BusinessException: 未提供任何删除条件时抛出
    """
    if app_id is None and user_id is None:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "必须提供 app_id 或 user_id 作为删除条件")

    query = ChatHistory.query.filter_by(is_delete=0)
    if app_id is not None:
        query = query.filter(ChatHistory.app_id == app_id)
    if user_id is not None:
        query = query.filter(ChatHistory.user_id == user_id)

    records = query.all()
    now = datetime.utcnow()
    for record in records:
        record.is_delete = 1
        record.update_time = now

    try:
        db.session.commit()
        return len(records)
    except Exception as e:
        db.session.rollback()
        raise BusinessException(ErrorCode.DATABASE_ERROR, f"批量删除对话记录失败: {str(e)}")