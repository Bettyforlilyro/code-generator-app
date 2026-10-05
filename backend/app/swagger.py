"""
Swagger / OpenAPI 文档初始化：定义 Swagger 配置模板 + 初始化 flasgger 扩展

当前使用 flasgger 库，Swagger UI 访问路径：http://localhost:5000/apidocs/

"""
from flasgger import Swagger

from backend.app.config import get_config


def init_swagger(app):
    """
    初始化 Swagger 文档

    Args:
        app: Flask 应用实例
    """
    cfg = get_config()

    # Swagger UI 配置
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,   # 所有端点都包含
                "model_filter": lambda tag: True,   # 所有模型都包含
            }
        ],
        "static_url_path": "/flasgger_static",
    }

    # OpenAPI 2.0 文档模板 —— host 从 Config 动态读取
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "代码生成器 API",
            "description": "前后端分离的代码生成器后端 API 文档",
            "version": "1.0.0",
            "contact": {
                "name": "zhy",
                "email": "908528702@qq.com"
            }
        },
        # 动态 host：开发时 localhost:5000，部署时替换为实际域名
        "host": f"localhost:{cfg.PORT}",
        "basePath": "/api/v1",  # API 前缀
        "schemes": ["http", "https"],
        # JWT 认证定义 —— 所有需要登录的接口统一标注 Bearer 安全
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Token 认证，格式: Bearer <token>",
            }
        },
        # 全局响应 Schema —— 前端/测试工程师直接从文档看到统一格式
        "definitions": {
            "ApiResponse": {
                "type": "object",
                "properties": {
                    "code": {"type": "integer", "description": "业务状态码", "example": 20000},
                    "message": {"type": "string", "description": "提示信息", "example": "操作成功"},
                    "data": {"type": "object", "description": "业务数据"},
                },
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "code": {"type": "integer", "description": "错误码", "example": 40000},
                    "message": {"type": "string", "description": "错误消息", "example": "请求参数错误"},
                    "data": {"type": "object", "description": "错误详情"},
                },
            },
        },
    }

    Swagger(app, config=swagger_config, template=swagger_template)
