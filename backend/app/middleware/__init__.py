"""
中间件包

横切关注点（CORS、日志、认证拦截等）统一注册入口。
新增中间件时，只需：
    1. 在 middleware/ 下创建模块，暴露 register(app) 函数
    2. 在本文件的 register_all() 中追加调用

注册顺序很重要：
    - logging_config 最先注册：确保后续所有模块的 logger 都有 handler
    - cors 在 request_logger 之前：让 OPTIONS 预检请求也被记录
    - 其他业务中间件按需插入
"""
from backend.app.middleware.cors import register_cors
from backend.app.middleware.my_logging import configure_logging
from backend.app.middleware.request_logger import register_request_logger


def register_all(app):
    """
    注册所有中间件到 Flask 应用

    Args:
        app: Flask 应用实例
    """
    configure_logging(app)
    register_cors(app)
    register_request_logger(app)
