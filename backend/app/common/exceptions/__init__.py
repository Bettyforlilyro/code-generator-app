"""
exceptions 包 —— 统一导出所有异常相关的公共 API

外部模块只需：from backend.app.common.exceptions import ErrorCode, BusinessException
无需写完整路径：from backend.app.common.exceptions.error_codes import ErrorCode
"""
from .error_codes import (
    ErrorCode,
    BusinessException,
    ParamValidationError,
    AuthenticationError,
    PermissionDeniedError,
    ResourceNotFoundError,
    AIServiceError,
    AIResponseParseError,
    FileOperationError,
)
from .exception_handlers import register_error_handlers

__all__ = [
    "ErrorCode",
    "BusinessException",
    "AuthenticationError",
    "PermissionDeniedError",
    "ParamValidationError",
    "ResourceNotFoundError",
    "AIServiceError",
    "AIResponseParseError",
    "FileOperationError",
    "register_error_handlers",
]
