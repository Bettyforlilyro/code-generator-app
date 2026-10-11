import logging
import os.path
import random
import shutil
import string
from datetime import datetime

from backend.app.common.enums import CodeFileType, DEFAULT_GENERATE_ROOT, DEFAULT_DEPLOY_ROOT
from backend.app.common.exceptions import ErrorCode, BusinessException
from backend.app.common.utils import (
    build_vue_project_sync,
    generate_app_page_screenshot_and_save_async,
)
from backend.app.extensions import db
from .deploy import get_default_nginx_manager
from .app_service import _get_app_or_raise

logger = logging.getLogger(__name__)


def _generate_deploy_key() -> str:
    """生成6位随机部署键"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


def deploy_app_svc(app_id: int, user_id: int) -> dict:
    """
    部署应用：复制代码文件到部署目录 + 启动 nginx（如未运行）

    Args:
        app_id: 应用 ID
        user_id: 当前登录用户 ID

    Returns:
        dict: 包含 deploy_key 和 deploy_url 的字典

    Raises:
        BusinessException: 应用不存在 / 无权限 / 代码未生成 / nginx 启动失败
    """
    app = _get_app_or_raise(app_id)

    if app.user_id != user_id:
        raise BusinessException(ErrorCode.FORBIDDEN, "没有权限部署该应用")
    if not app.code_gen_type:
        raise BusinessException(ErrorCode.APP_NOT_FOUND, "应用实际未生成，请确认是否已生成")

    # 生成/复用 deploy_key
    if not app.deploy_key:
        app.deploy_key = _generate_deploy_key()

    # 确定源目录
    source_dir = os.path.join(DEFAULT_GENERATE_ROOT, f"{app.code_gen_type}_{app.id}")
    if not os.path.isdir(source_dir):
        raise BusinessException(ErrorCode.APP_NOT_FOUND, "应用代码不存在，请确认是否已生成")

    # Vue 项目：先构建再部署 dist
    if app.code_gen_type == CodeFileType.VUE_PROJECT:
        source_dir = _prepare_vue_build(source_dir)

    # 复制文件到部署目录
    target_dir = os.path.join(DEFAULT_DEPLOY_ROOT, app.deploy_key)
    try:
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    except Exception as e:
        raise BusinessException(ErrorCode.INTERNAL_ERROR, f"部署应用失败: {str(e)}")

    app.deploy_time = datetime.utcnow()
    db.session.commit()
    deploy_url = f"http://localhost/dist/{app.deploy_key}"

    # 确保 nginx 运行
    _ensure_nginx_running()

    # 异步截图
    generate_app_page_screenshot_and_save_async(app_id, deploy_url)

    return {
        "deploy_key": app.deploy_key,
        "deploy_url": deploy_url,
    }


def _prepare_vue_build(source_dir: str) -> str:
    """Vue 项目构建，返回构建产物的 dist 目录"""
    if not build_vue_project_sync(source_dir):
        raise BusinessException(ErrorCode.INTERNAL_ERROR, "Vue项目构建失败")
    dist_dir = os.path.join(source_dir, "dist")
    if not os.path.isdir(dist_dir):
        raise BusinessException(ErrorCode.INTERNAL_ERROR, "Vue项目构建失败，dist目录不存在")
    return dist_dir


def _ensure_nginx_running() -> None:
    """确保 nginx 运行，启动失败则抛异常"""
    nginx = get_default_nginx_manager()
    if not nginx.is_running():
        if not nginx.start():
            raise BusinessException(ErrorCode.INTERNAL_ERROR, "启动 nginx 失败")
