from flask import Flask, make_response, request
from backend.app.common.exceptions.exception_handlers import register_error_handlers
from backend.app.swagger import init_swagger
from flask_cors import CORS


def create_app(config=None):
    """
    创建Flask应用工厂

    Args:
        config: 配置字典（可选）

    Returns:
        Flask应用实例
    """
    app = Flask(__name__)
    # 关闭strict_slashes，保证不对末尾斜杠进行重定向
    app.url_map.strict_slashes = False
    # 开启CORS，支持跨域请求
    CORS(
        app,
        resources=r"/*",
        supports_credentials=True,
        origins="*",
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
        allow_headers=["Content-Type", "Authorization", "X-Request-With", "Accept", "Origin"],
        expose_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    # 加载配置
    if config:
        app.config.update(config)
    # 注册v1版本所有蓝图，代码在backend/app/api/v1/__init__.py中
    from backend.app.api.v1 import register_v1_blueprints
    register_v1_blueprints(app)

    # 注册全局异常处理器
    register_error_handlers(app)

    # 初始化Swagger文档
    init_swagger(app)

    return app
