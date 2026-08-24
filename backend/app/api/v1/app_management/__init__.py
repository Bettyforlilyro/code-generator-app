from flask import Blueprint

# 创建应用管理蓝图
app_management_bp = Blueprint('app_management', __name__, url_prefix='app')


def register_app_routes():
    """
    注册应用管理相关路由

    这个函数应该在蓝图被注册到app之前调用
    """
    # 延迟导入路由，确保在蓝图注册前完成所有路由定义
    from backend.app.api.v1.app_management import manage_app
