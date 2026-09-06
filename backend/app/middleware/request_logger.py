"""
请求访问日志中间件

通过 Flask 的 before_request / after_request 钩子记录每个请求的：
    - HTTP 方法 + URL
    - 响应状态码
    - 耗时（毫秒）
    - 客户端 IP

噪音路径（健康检查、Swagger）自动过滤，不写入日志。
"""
import time
import logging

from flask import request, g

logger = logging.getLogger(__name__)

# 这些路径不记录（Swagger 文档、健康检查、静态文件等）
_SKIP_PATHS = {
    "/health",
    "/swagger",
    "/swagger/",
    "/swagger/index.html",
    "/swagger-json",
    "/swagger-config",
    "/favicon.ico",
    "/static",
}


def register_request_logger(app):
    """
    注册请求日志钩子

    Args:
        app: Flask 应用实例
    """

    @app.before_request
    def _start_timer():
        """记录请求开始时间"""
        g._request_start_time = time.perf_counter()

    @app.after_request
    def _log_response(response):
        """在响应发送前记录访问日志"""
        # 1. 过滤噪音路径（以 _SKIP_PATHS 或 _SKIP_PATHS 开头的路径）
        path = request.path.rstrip("/") or "/"
        if any(path.startswith(skip_path) or path == skip_path for skip_path in _SKIP_PATHS):
            return response

        # 2. 计算耗时
        start = getattr(g, "_request_start_time", None)
        elapsed_ms = (time.perf_counter() - start) * 1000 if start else -1

        # 3. 获取客户端 IP（兼容反向代理场景，X-Forwarded-For 优先）
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "-")
        if client_ip and "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()

        # 4. 分级记录：慢请求（>10min）和错误响应（>=400）用 WARNING
        status = response.status_code
        method = request.method
        level = logging.WARNING if (status >= 400 or elapsed_ms > 600 * 1000) else logging.INFO

        logger.log(
            level,
            "%s %s %s -> %d (%.1fms) from %s",
            client_ip, method, path, status, elapsed_ms, client_ip,
        )

        return response
