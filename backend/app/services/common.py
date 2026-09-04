"""
Service 层公共工具函数 / 装饰器

被各业务 Service 复用，不依赖任何业务 Model。
"""
import functools
import logging
from typing import Callable, Iterable

from backend.app.common.exceptions.error_codes import BusinessException, ErrorCode
from backend.app.extensions.db_instance import db

logger = logging.getLogger(__name__)


# ==================== 分页排序校验 ====================

def validate_sort_params(
    sort_field: str,
    sort_order: str,
    allowed_fields: Iterable[str],
) -> None:
    """
    统一校验分页查询的排序参数

    Args:
        sort_field: 排序字段名
        sort_order: 排序方向，仅支持 'asc' / 'desc'
        allowed_fields: 允许的排序字段集合

    Raises:
        BusinessException: 参数非法
    """
    allowed = set(allowed_fields)
    if sort_field not in allowed:
        raise BusinessException(
            ErrorCode.INVALID_PARAMETER,
            f"排序字段无效，允许的字段: {', '.join(sorted(allowed))}",
        )
    if sort_order not in ('asc', 'desc'):
        raise BusinessException(
            ErrorCode.INVALID_PARAMETER,
            "排序方向无效，仅支持 asc 或 desc",
        )


# ==================== 事务装饰器 ====================

def db_transaction(error_message: str = "数据库操作失败"):
    """
    自动管理 SQLAlchemy 事务的装饰器

    功能：
    - 函数正常返回时自动 commit
    - 抛出 BusinessException 时 rollback 后直接 re-raise
    - 抛出其他 Exception 时 rollback 后包装成 BusinessException(DATABASE_ERROR)

    Usage:
        @db_transaction("创建对话记录失败")
        def create_chat_history(...):
            record = ChatHistory(...)
            db.session.add(record)
            return record
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                db.session.commit()
                return result
            except BusinessException:
                db.session.rollback()
                raise
            except Exception as e:
                db.session.rollback()
                logger.error(f"{error_message}: {str(e)}")
                raise BusinessException(ErrorCode.DATABASE_ERROR, f"{error_message}: {str(e)}")
        return wrapper
    return decorator
