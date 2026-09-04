from flask import Blueprint

# 创建代码生成器蓝图
code_bp = Blueprint('code_bp', __name__, url_prefix="code")


def register_code_generate_routes():
    """
    注册代码生成器相关路由
    """
    # 延迟导入路由，确保在蓝图注册前完成所有路由定义
    from backend.app.api.v1.code_generate_api import code_generate, code_resource
