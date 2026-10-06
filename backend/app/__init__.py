from flask import Flask

from backend.app.common.exceptions import register_error_handlers
from backend.app.middleware import register_all as register_middleware
from backend.app.swagger import init_swagger


def create_app(config=None):
    """
    创建Flask应用工厂

    初始化顺序：
        1. 创建 Flask 实例 + 加载配置
        2. 初始化所有扩展（主要是 ORM 层）
        3. 注册中间件（logging → 限流 → CORS → request_logger）
        4. 注册蓝图（业务路由）
        5. 注册全局异常处理器
        6. 初始化 Swagger 文档（最后，因为需要所有路由已注册完毕才能生成 spec）

    Args:
        config: 配置字典（可选，内部已通过 get_config() 从 Config 类注入）

    Returns:
        Flask应用实例
    """
    app = Flask(__name__)
    # 关闭 strict_slashes，不对末尾斜杠进行重定向
    app.url_map.strict_slashes = False

    # 1. 加载配置
    if config:
        app.config.update(config)

    # 2. 初始化扩展（db 等 ORM 对象）
    from backend.app.extensions.db_instance import db
    db.init_app(app)

    # 3. 注册中间件（CORS、限流、日志、请求日志等横切关注点）
    register_middleware(app)

    # 4. 注册 v1 版本所有蓝图，代码在 backend/app/api/v1/__init__.py 中
    from backend.app.api.v1 import register_v1_blueprints
    register_v1_blueprints(app)

    # 5. 注册全局异常处理器
    register_error_handlers(app)

    # 6. 初始化 Swagger 文档（最后：等所有路由已注册，spec 才能正确生成）
    init_swagger(app)

    return app
