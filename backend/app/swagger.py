from flasgger import Swagger


def init_swagger(app):
    """
    初始化Swagger文档

    Args:
        app: Flask应用实例
    """
    # 可以对swagger UI深度定制，这里使用默认的算了
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,  # 所有端点都包含
                "model_filter": lambda tag: True,  # 所有模型都包含
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui_prefix": "/docs",  # Swagger UI访问路径
        "swagger_ui_bundle_url": None,
        "swagger_ui_css_url": None,
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "代码生成器API",
            "description": "前后端分离的代码生成器后端API文档",
            "version": "1.0.0",
            "contact": {
                "name": "开发团队",
                "email": "dev@example.com"
            }
        },
        "host": "localhost:5000",
        "basePath": "/api",
        "schemes": ["http"],
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Token认证，格式: Bearer <token>"
            }
        },
        "definitions": {
            "ApiResponse": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "integer",
                        "description": "业务状态码",
                        "example": 20000
                    },
                    "message": {
                        "type": "string",
                        "description": "提示信息",
                        "example": "操作成功"
                    },
                    "data": {
                        "type": "object",
                        "description": "业务数据"
                    }
                }
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "integer",
                        "description": "错误码",
                        "example": 40000
                    },
                    "message": {
                        "type": "string",
                        "description": "错误消息",
                        "example": "请求参数错误"
                    },
                    "data": {
                        "type": "object",
                        "description": "错误详情"
                    }
                }
            }
        },
        "responses": {
            "SuccessResponse": {
                "description": "成功响应",
                "schema": {
                    "$ref": "#/definitions/ApiResponse"
                }
            },
            "ErrorResponse": {
                "description": "错误响应",
                "schema": {
                    "$ref": "#/definitions/ErrorResponse"
                }
            }
        }
    }

    # Swagger(app, config=swagger_config, template=swagger_template)

    Swagger(app)
