"""
CORS 跨域中间件

从 app/__init__.py 中剥离出来，保持参数完全一致，仅封装位置。
"""
from flask_cors import CORS


def register_cors(app):
    """
    注册 CORS 中间件

    Args:
        app: Flask 应用实例
    """
    CORS(
        app,
        resources=r"/*",
        supports_credentials=True,
        origins="*",
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
        allow_headers=["Content-Type", "Authorization", "X-Request-With", "Accept", "Origin"],
        expose_headers=["Authorization", "Content-Type", "Content-Disposition"],
        max_age=600,
    )
