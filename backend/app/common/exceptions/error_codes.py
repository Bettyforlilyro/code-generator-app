from enum import Enum


class ErrorCode(Enum):
    """
    业务错误码枚举

    错误码分区规范（参考 HTTP 状态码语义 + 业务分层）：
    - 20000-29999: 成功类状态码
    - 40000-40099: 通用客户端请求错误（参数校验、格式错误）
    - 40100-40199: 认证错误（未登录、Token 问题）
    - 40300-40399: 授权错误（权限不足）
    - 40400-40499: 资源未找到（按业务细分）
    - 40900-40999: 业务冲突/重复
    - 42900-42999: 限流
    - 50000-50099: 通用服务器内部错误
    - 50100-50199: 数据库错误
    - 50200-50299: AI / LLM 服务错误（代码生成核心依赖）
    - 50300-50399: 文件处理错误（代码落盘、静态资源）
    - 50400-50499: 其他业务逻辑处理失败
    """

    # ==================== 成功状态码 (20000-29999) ====================
    SUCCESS = (20000, "操作成功")

    # ==================== 通用请求错误 (40000-40099) ====================
    BAD_REQUEST = (40000, "请求参数错误")
    INVALID_JSON = (40001, "JSON格式错误")
    MISSING_PARAMETER = (40002, "缺少必要参数")
    INVALID_PARAMETER = (40003, "参数值无效")

    # ==================== 认证相关错误 (40100-40199) ====================
    UNAUTHORIZED = (40100, "未登录或登录已过期")
    TOKEN_INVALID = (40101, "Token无效")
    TOKEN_EXPIRED = (40102, "Token已过期")

    # ==================== 授权相关错误 (40300-40399) ====================
    FORBIDDEN = (40300, "没有权限访问")
    PERMISSION_DENIED = (40301, "权限不足")

    # ==================== 资源未找到 (40400-40499) ====================
    NOT_FOUND = (40400, "资源不存在")
    APP_NOT_FOUND = (40401, "应用不存在")
    USER_NOT_FOUND = (40402, "用户不存在")
    CHAT_HISTORY_NOT_FOUND = (40403, "对话历史不存在")

    # ==================== 业务冲突/重复 (40900-40999) ====================
    CONFLICT = (40900, "资源冲突")
    DUPLICATE_DATA = (40901, "数据重复")
    USER_NAME_EXISTS = (40902, "用户名已存在")

    # ==================== 限流 (42900-42999) ====================
    TOO_MANY_REQUESTS = (42900, "请求过于频繁，请稍后重试")

    # ==================== 通用服务器内部错误 (50000-50099) ====================
    INTERNAL_ERROR = (50000, "服务器内部错误")

    # ==================== 数据库错误 (50100-50199) ====================
    DATABASE_ERROR = (50100, "数据库操作失败")
    DATABASE_CONNECTION_ERROR = (50101, "数据库连接失败")

    # ==================== AI / LLM 服务错误 (50200-50299) ====================
    AI_SERVICE_ERROR = (50200, "AI服务调用失败")
    AI_RESPONSE_PARSE_ERROR = (50201, "AI响应解析失败")
    AI_TIMEOUT = (50202, "AI服务请求超时")
    AI_RATE_LIMITED = (50203, "AI服务请求频率超限")

    # ==================== 文件处理错误 (50300-50399) ====================
    FILE_OPERATION_ERROR = (50300, "文件操作失败")
    FILE_WRITE_ERROR = (50301, "文件写入失败")
    FILE_NOT_FOUND = (50302, "文件不存在")

    # ==================== 业务逻辑处理失败 (50400-50499) ====================
    BUSINESS_LOGIC_ERROR = (50400, "业务处理失败")

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
    """资源未找到异常（通用）"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.NOT_FOUND, message, data)


class AIServiceError(BusinessException):
    """AI 服务调用异常（网络错误、服务不可用等）"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.AI_SERVICE_ERROR, message, data)


class AIResponseParseError(BusinessException):
    """AI 响应解析异常（JSON 格式不符、Pydantic 校验失败等）"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.AI_RESPONSE_PARSE_ERROR, message, data)


class FileOperationError(BusinessException):
    """文件操作异常（写入、权限、路径不存在等）"""

    def __init__(self, message: str = None, data: dict = None):
        super().__init__(ErrorCode.FILE_OPERATION_ERROR, message, data)