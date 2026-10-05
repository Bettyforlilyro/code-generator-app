"""
限流中间件（Flask-Limiter 封装）

职责：
    1. 全局 IP 兜底限流（default_limits）—— 没加显式装饰器的接口都走这个
    2. 通用多维度限流装饰器 my_limiter —— 业务层通过 dict 参数灵活组合

使用示例：
    # 用户 3/min + IP 10/min 双重限流
    @my_limiter({"user": "3 per minute", "ip": "10 per minute"})
    def func():
        ...

    # 仅 IP 维度 5/min（登录接口防暴力破解）
    @my_limiter({"ip": "5 per minute"})
    def login_user():
        ...

"""
import logging

from flask import Flask, g, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.app.common.exceptions.error_codes import ErrorCode
from backend.app.config import get_config
from backend.app.schemas.responses.BaseResponse import error_response

_logger = logging.getLogger(__name__)

# ── 全局 limiter 单例，默认限流器 ──
limiter = Limiter(
    key_func=get_remote_address,  # 先随便给一个，init_app 时会覆盖
    default_limits=["300 per minute"],  # 全局温和兜底：每 IP 每分钟 300 次
    storage_uri=None,  # 等 init_app 时从 Config 注入
    # flask-limiter 支持的限流策略：fixed-window, moving-window, sliding-window-counter；
    # 令牌桶 token-bucket 未内置，如果想使用，需要自定义实现，复杂度较高
    strategy="fixed-window",  # 固定窗口算法，简单可靠（token-bucket 更平滑但略复杂）
)


def my_limiter(limits: dict):
    """
    通用多维度限流装饰器
    limits 的每个条目对应一个独立的限流维度，任一超限即拦截。

    Args:
        limits: {维度: 限流频次}
            维度 key 目前支持三种形式：
                - "user" (str)  →  登录用户 ID（未登录自动回退 IP）
                - "ip"   (str)  →  客户端 IP
                - callable       →  自定义 key_func，签名 () -> str
            限流频次 value 遵循 Flask-Limiter 语法，如 "3 per minute"、"10/hour"、"100 per day"

    Returns:
        装饰器函数，用法同普通 Flask 装饰器

    Raises:
        ValueError: limits 字典为空，或 key 是无法识别的字符串

    使用示例：
        # 用户 10/min + IP 20/min 双重保护（LLM token 贵）
        @my_limiter({"user": "10 per minute", "ip": "20 per minute"})
        def my_func():
            ...

        # 登录接口：仅 IP 维度 5/min（防暴力破解）
        @my_limiter({"ip": "5 per minute"})
        def login_user():
            ...

        # 也可以混合 callable 和字符串
        @my_limiter({"ip": "30 per minute", lambda: request.path: "60 per minute"})
        def some_api():
            ...
    """
    if not limits:
        raise ValueError("my_limiter() 的 limits 参数不能为空")

    def decorator(f):
        for key, rate in limits.items():
            key_func = _resolve_key(key)
            f = limiter.limit(rate, key_func=key_func)(f)
        return f
    return decorator


def _resolve_key(key):
    """
    把 my_limiter 的 dict key 解析成 Flask-Limiter 所需的 key_func

    Args:
        key: 字符串别名 ("user" / "ip") 或自定义 callable

    Returns:
        callable: () -> str
    """
    if callable(key):
        return key

    mapping = {
        "user": _get_default_key,
        "ip": get_remote_address,
    }
    if key in mapping:
        return mapping[key]

    raise ValueError(
        f"my_limiter() 不认识的 key: {key!r}\n"
        f"支持: 'user', 'ip', 或直接传一个 callable (签名 () -> str)"
    )


# 内部工具
def _get_default_key() -> str:
    """获取全局默认的限流 key：登录用户优先用 user_name作为 key，未登录回退到 IP

    Flask-Limiter 的 key_func 签名是 () -> str，所以需要函数包一层。
    """
    try:
        current_user_name = getattr(g, 'current_user_name', None)
        if current_user_name is not None:
            return f"user:{current_user_name}"
    except Exception:
        # 无请求上下文 / g.current_user_name 不存在（如未登录的接口）
        pass
    return f"ip:{get_remote_address()}"


# 为 flask app 注册限流中间件
def register_rate_limiter(app: Flask):
    """
    初始化 Flask-Limiter + 注册 429 错误处理器

    Args:
        app: Flask 应用实例
    """
    storage_url = get_config().RATE_LIMIT_STORAGE_URL
    _logger.info(f"限流存储后端: {storage_url}")

    limiter.init_app(app)
    # 全局 Limiter 设置默认 key_func：用更智能的用户优先策略
    # 自定义 my_limiter 里每个维度都显式传了 key_func，不受此影响
    limiter.key_func = _get_default_key
    # 注入存储 URI（init_app 之后才能通过 Limiter 实例的 _storage_uri 属性设）
    limiter._storage_uri = storage_url

    _logger.info(f"限流初始化完成: storage={storage_url}")

    @app.errorhandler(429)
    def handle_limited_request(e):
        """Flask-Limiter 触发限流时，返回项目统一的错误响应格式"""
        _logger.warning(
            f"[RATE_LIMITED] user={_get_default_key()} path={request.path} "
            f"method={request.method} detail={e.description}"
        )
        return error_response(
            ErrorCode.TOO_MANY_REQUESTS,
            message=f"{ErrorCode.TOO_MANY_REQUESTS.message}（{e.description}）",
            http_status=429,
        )
