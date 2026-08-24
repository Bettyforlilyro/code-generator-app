from enum import Enum


class ErrorCode(Enum):
    """
    业务错误码枚举

    错误码设计规范：
    - 20000-29999: 成功类状态码
    - 40000-49999: 客户端错误（请求参数、认证、授权等）
    - 50000-59999: 服务端错误（系统异常、业务处理失败等）
    """

    # ==================== 成功状态码 (20000-29999) ====================
    SUCCESS = (20000, "操作成功")

    # ==================== 客户端错误 (40000-49999) ====================
    # 通用请求错误 (40000-40099)
    BAD_REQUEST = (40000, "请求参数错误")
    INVALID_JSON = (40001, "JSON格式错误")
    MISSING_PARAMETER = (40002, "缺少必要参数")
    INVALID_PARAMETER = (40003, "参数值无效")

    # 认证相关错误 (40100-40199)
    UNAUTHORIZED = (40100, "未登录或登录已过期")
    TOKEN_INVALID = (40101, "Token无效")
    TOKEN_EXPIRED = (40102, "Token已过期")

    # 授权相关错误 (40300-40399)
    FORBIDDEN = (40300, "没有权限访问")
    PERMISSION_DENIED = (40301, "权限不足")

    # 资源相关错误 (40400-40499)
    NOT_FOUND = (40400, "资源不存在")
    RESOURCE_NOT_FOUND = (40401, "指定的资源未找到")

    # 业务逻辑错误 (40500-40599)
    METHOD_NOT_ALLOWED = (40500, "请求方法不允许")
    CONFLICT = (40501, "资源冲突")
    DUPLICATE_DATA = (40502, "数据重复")
    APP_NOT_FOUND = (40503, "应用不存在")

    # 限流相关错误 (42900-42999)
    TOO_MANY_REQUESTS = (42900, "请求过于频繁，请稍后重试")

    # ==================== 服务端错误 (50000-59999) ====================
    # 通用服务器错误 (50000-50099)
    INTERNAL_ERROR = (50000, "服务器内部错误")
    SERVICE_UNAVAILABLE = (50001, "服务暂时不可用")

    # 数据库错误 (50100-50199)
    DATABASE_ERROR = (50100, "数据库操作失败")
    DATABASE_CONNECTION_ERROR = (50101, "数据库连接失败")

    # 第三方服务错误 (50200-50299)
    THIRD_PARTY_ERROR = (50200, "第三方服务调用失败")

    # 文件处理错误 (50300-50399)
    FILE_UPLOAD_ERROR = (50300, "文件上传失败")
    FILE_NOT_FOUND = (50301, "文件不存在")

    def __init__(self, code: int, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> int:
        return self._code

    @property
    def message(self) -> str:
        return self._message


class BusinessException(Exception):
    """
    业务异常基类

    Args:
        error_code: 错误码枚举
        message: 自定义错误消息（可选，如果不提供则使用错误码默认消息）
        data: 附加的错误详情数据（可选）
    """

    def __init__(self, error_code: ErrorCode, message: str = None, data: dict = None):
        self.error_code = error_code
        self.code = error_code.code
        self.message = message or error_code.message
        self.data = data
        super().__init__(self.message)


class ParamValidationError(BusinessException):
    """参数验证异常"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.BAD_REQUEST, message, data)


class AuthenticationError(BusinessException):
    """认证异常"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.UNAUTHORIZED, message, data)


class PermissionDeniedError(BusinessException):
    """权限拒绝异常"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.FORBIDDEN, message, data)


class ResourceNotFoundError(BusinessException):
    """资源未找到异常"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.NOT_FOUND, message, data)
