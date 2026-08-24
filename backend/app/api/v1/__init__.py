from flask import Blueprint

# 创建v1版本主蓝图
api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


def register_v1_blueprints(app):
    """
    注册v1版本的所有子蓝图

    Args:
        app: Flask应用实例
    """

    from backend.app.api.v1.user_management import user_management_bp, register_user_routes
    from backend.app.api.v1.code_generate_api import code_generate_bp, register_code_generate_routes
    from backend.app.api.v1.app_management import app_management_bp, register_app_routes

    # 先注册各个api路由
    register_user_routes()
    register_code_generate_routes()
    register_app_routes()

    # 注册子蓝图到主蓝图
    api_v1_bp.register_blueprint(user_management_bp)
    api_v1_bp.register_blueprint(code_generate_bp)
    api_v1_bp.register_blueprint(app_management_bp)

    # 最后注册主蓝图到app
    app.register_blueprint(api_v1_bp)
