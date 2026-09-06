"""
全局 logging 配置

只需在应用启动时调用 configure_logging(app) 一次，
之后所有模块的 `logger = logging.getLogger(__name__)` 都会自动使用这里的配置。

采用 双 handler + 分级过滤 的策略：
    - INFO 及以上：输出到控制台（开发环境）
    - WARNING 及以上：输出到文件（生产环境），自动按天轮转
"""
import logging
import logging.handlers
import os
from pathlib import Path

# 日志路径：项目根目录下的 logs/
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "logs"


def configure_logging(app):
    """
    配置 Flask 应用的全局日志（幂等：重复调用不会重复添加 handler）

    Args:
        app: Flask 应用实例
    """
    # 1. 防止 Flask/Werkzeug 已经配过 handler 后重复追加（常见于调试模式的重载）
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # 已经配置过了（Flask debug reloader 触发第二次 create_app 时）
        return

    # 2. 日志级别：DEBUG 模式下打 DEBUG，否则 INFO
    log_level = logging.DEBUG if app.config.get("DEBUG", False) else logging.INFO

    # 3. 统一日志格式（控制台简洁，文件带更多上下文）
    console_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 4. 控制台 handler（INFO 及以上全打）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_fmt)

    # 5. 文件 handler（WARNING 及以上才写文件，避免日志膨胀）
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=LOG_DIR / "app.log",
            when="MIDNIGHT",      # 每天轮转
            backupCount=14,       # 保留最近 14 天
            encoding="utf-8",
        )
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(file_fmt)
        has_file_handler = True
    except (OSError, PermissionError):
        # 无日志目录权限（如只读文件系统的容器环境），降级为仅控制台
        app.logger.warning(f"日志目录不可写: {LOG_DIR}，跳过文件 handler")
        has_file_handler = False

    # 6. 挂载到 root logger，这样所有模块的 getLogger(__name__) 都会继承
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    if has_file_handler:
        root_logger.addHandler(file_handler)

    # 7. 降低第三方库的噪音（SQLAlchemy、LangChain 等默认 DEBUG 非常啰嗦）
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

    app.logger.info(f"日志配置完成，级别={logging.getLevelName(log_level)}，日志目录={LOG_DIR}")
