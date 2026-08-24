from flask import Blueprint

# 创建用户管理蓝图
user_management_bp = Blueprint('user_management', __name__, url_prefix='user')


def register_user_routes():
    """
    注册用户管理相关路由

    这个函数应该在蓝图被注册到app之前调用
    """
    # 延迟导入路由，确保在蓝图注册前完成所有路由定义
    from backend.app.api.v1.user_management import register, login, manage_user
