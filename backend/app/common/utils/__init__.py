"""
utils 包 —— 通用工具函数集

只导出公共 API，内部模块互相之间仍用相对导入。
"""
# 认证相关（auth_service.py 高频用）
from .auth import (
    login_required,
    role_required,
    generate_access_token,
    generate_refresh_token,
    verify_access_token,
    verify_refresh_token,
)

# 缓存（ai_common 高频用）
from .cache import MemoryCache

# 代码文件保存（ai_generator_facade + graph/nodes 高频用）
from .code_file_saver import CodeFileSaverFactory, CodeFileSaver

# 图片上传（graph/nodes/image_tools 用）
from .upload_image import upload_image_to_bed

# 随机图片（auth_service 用）
from .get_random_picture import get_random_avatar, get_random_bz

# Vue 项目构建（app_service 用）
from .build_vue_project import build_vue_project_sync, build_vue_project_async

# 截图（app_service + generate 内部用）
from .generate_app_page_screenshot import (
    generate_app_page_screenshot_and_save_async,
    generate_app_page_screenshot_and_save,
)

# LLM 响应解析（ai_common 用）
from .parse_llm_response import parse_llm_json_response

# Token 估算（ai_common 用）
from .estimate_tokens import estimate_tokens

# 请求辅助（通用）
from .request_helpers import parse_pagination_args

# 无头浏览器截图
from .save_webpage_screenshot import take_screenshot_and_save

__all__ = [
    "login_required",
    "role_required",
    "generate_access_token",
    "generate_refresh_token",
    "verify_access_token",
    "verify_refresh_token",
    "MemoryCache",
    "CodeFileSaverFactory",
    "CodeFileSaver",
    "upload_image_to_bed",
    "get_random_avatar",
    "get_random_bz",
    "build_vue_project_sync",
    "build_vue_project_async",
    "generate_app_page_screenshot_and_save_async",
    "generate_app_page_screenshot_and_save",
    "parse_llm_json_response",
    "estimate_tokens",
    "parse_pagination_args",
    "take_screenshot_and_save",
]
