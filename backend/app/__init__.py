from flask import Flask

from backend.app.common.exceptions.exception_handlers import register_error_handlers
from backend.app.middleware import register_all as register_middleware
from backend.app.swagger import init_swagger


def create_app(config=None):
    """
    创建Flask应用工厂

    初始化顺序（重要）：
        1. 创建 Flask 实例 + 加载配置
        2. 注册中间件（logging → CORS → request_logger）
        3. 注册蓝图（业务路由）
        4. 注册全局异常处理器
        5. 初始化 Swagger

    Args:
        config: 配置字典（可选）

    Returns:
        Flask应用实例
    """
    app = Flask(__name__)
    # 关闭 strict_slashes，不对末尾斜杠进行重定向
    app.url_map.strict_slashes = False

    # 1. 加载配置
    if config:
        app.config.update(config)

    # 2. 注册中间件（CORS、日志、请求日志等横切关注点）
    register_middleware(app)

    # 3. 注册 v1 版本所有蓝图，代码在 backend/app/api/v1/__init__.py 中
    from backend.app.api.v1 import register_v1_blueprints
    register_v1_blueprints(app)

    # 4. 注册全局异常处理器
    register_error_handlers(app)

    # 5. 初始化 Swagger 文档
    init_swagger(app)

    return app