import logging
import traceback

from flask import request
from werkzeug.exceptions import HTTPException
from .error_codes import BusinessException, ErrorCode
from ...schemas.responses import BaseResponse

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """
    注册全局异常处理器

    分为三类：
    1. 业务异常处理（BusinessException及其子类）
    2. HTTP协议错误处理（404, 405等）
    3. 未捕获的系统异常处理（兜底）

    Args:
        app: Flask应用实例
    """

    # ==================== 1. 业务异常处理 ====================
    @app.errorhandler(BusinessException)
    def handle_business_exception(error: BusinessException):
        """
        处理业务逻辑异常

        这类异常是由业务代码主动抛出的，用于表示业务规则违反
        例如：参数验证失败、权限不足、资源不存在等
        """
        logger.warning(
            f"Business Exception: code={error.code}, message={error.message}, "
            f"path={request.path}, method={request.method}"
        )
        return BaseResponse.error_response(error.error_code, error.message, error.data)

    # ==================== 2. HTTP协议错误处理 ====================
    # ==================== 2. HTTP协议错误处理 ====================
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """
        处理HTTP协议层错误

        Flask在路由匹配失败、方法不允许等情况下会抛出HTTPException
        需要将这些HTML响应转换为统一的JSON格式，并根据不同的HTTP状态码
        映射到对应的业务错误码，便于前端和后端统一处理

        常见场景及映射关系：
        - 400: BAD_REQUEST (40000) - 请求参数错误
        - 401: UNAUTHORIZED (40100) - 未认证
        - 403: FORBIDDEN (40300) - 无权限访问
        - 404: NOT_FOUND (40400) - 资源不存在
        - 405: METHOD_NOT_ALLOWED (40500) - 请求方法不允许
        - 409: CONFLICT (40501) - 资源冲突
        - 429: TOO_MANY_REQUESTS (42900) - 请求过于频繁
        - 其他: INTERNAL_ERROR (50000) - 服务器内部错误
        """
        logger.warning(
            f"HTTP Exception: code={error.code}, description={error.description}, "
            f"path={request.path}, method={request.method}"
        )

        http_code_to_error_code = {
            400: ErrorCode.BAD_REQUEST,
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.METHOD_NOT_ALLOWED,
            409: ErrorCode.CONFLICT,
            429: ErrorCode.TOO_MANY_REQUESTS,
        }

        error_code = http_code_to_error_code.get(error.code, ErrorCode.INTERNAL_ERROR)
        custom_message = error_code.message

        return BaseResponse.error_response(error_code, custom_message, http_status=error.code)

    # ==================== 3. 系统异常兜底处理 ====================
    @app.errorhandler(Exception)
    def handle_generic_exception(error: Exception):
        """
        处理所有未捕获的系统异常（兜底）

        这是最后一道防线，捕获所有未被上述处理器处理的异常
        包括：数据库连接失败、第三方API调用异常、代码bug等
        """
        logger.error(
            f"Unhandled System Exception: path={request.path}, method={request.method}\n"
            f"Error Type: {type(error).__name__}\n"
            f"Error: {str(error)}\n"
            f"Traceback: {traceback.format_exc()}"
        )

        return BaseResponse.error_response(ErrorCode.INTERNAL_ERROR, "Unknown Internal Error!")
