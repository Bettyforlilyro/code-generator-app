"""
应用管理 Service 层

集中封装 AppModel 模型的所有业务逻辑和数据库操作。
"""
import logging
import os.path
import random
import shutil
import string
import subprocess
from datetime import datetime
from typing import Optional

from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT, DEFAULT_DEPLOY_ROOT, NGINX_PATH
from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.get_random_picture import get_random_bz
from backend.app.extensions.db_instance import db
from backend.app.models.app_model import AppModel
from backend.app.models.user import User
from backend.app.schemas.requests.app_management_request import (
    AppCreateRequest, AppUpdateRequest, AdminAppUpdateRequest
)
from backend.app.schemas.responses.app_management_response import (
    AppDetailResponse, AppListResponse, AppCreateResponse
)
from backend.app.schemas.responses.user_management_response import UserSummaryResponse
from backend.app.services.common import validate_sort_params

logger = logging.getLogger(__name__)


# ==================== 创建 ====================

def create_app_svc(user_id: int, req: AppCreateRequest) -> AppCreateResponse:
    """
    创建新应用

    Args:
        user_id: 创建应用的用户 ID
        req: 应用创建请求

    Returns:
        AppCreateResponse: 包含应用 ID、应用名称、应用覆盖范围、初始化提示的响应模型

    """
    app_name = req.app_name if req.app_name else req.init_prompt[:20]
    app_coverage = req.app_coverage if req.app_coverage else get_random_bz()

    new_app = AppModel(
        app_name=app_name,
        code_gen_type=req.code_gen_type,
        app_coverage=app_coverage,
        init_prompt=req.init_prompt,
        user_id=user_id,
    )
    db.session.add(new_app)
    db.session.commit()

    return AppCreateResponse(**new_app.to_dict())


# ==================== 更新 ====================

def update_app_svc(app_id: int, user: User, req: AppUpdateRequest | AdminAppUpdateRequest) -> None:
    """
    更新应用信息（用户修改自己的应用 / 管理员可改 priority）

    Args:
        app_id: 应用 ID
        user: 当前登录用户
        req: 应用更新请求

    Raises:
        BusinessException: 应用不存在或权限不足
    """
    app = _get_app_or_raise(app_id)
    is_admin = user.user_role == UserRole.ADMIN

    if not is_admin and app.user_id != user.id:
        raise BusinessException(ErrorCode.PERMISSION_DENIED, "无权修改此应用")

    is_updated = False
    if req.app_name is not None and req.app_name != app.app_name:
        app.app_name = req.app_name
        is_updated = True
    if req.app_coverage is not None and req.app_coverage != app.app_coverage:
        app.app_coverage = req.app_coverage
        is_updated = True
    if is_admin and hasattr(req, 'priority'):
        if req.priority is not None and req.priority != app.priority:
            app.priority = req.priority
            is_updated = True

    if is_updated:
        app.edit_time = datetime.utcnow()
        db.session.commit()


# ==================== 删除 ====================

def delete_app_svc(app_id: int, user: User, delete_chat_history_fn) -> None:
    """
    软删除应用（同时清理关联对话历史）

    Args:
        app_id: 应用 ID
        user: 当前登录用户
        delete_chat_history_fn: 外部注入的对话历史删除函数，参数为 app_id
    """
    app = _get_app_or_raise(app_id)

    if user.user_role != UserRole.ADMIN and app.user_id != user.id:
        raise BusinessException(ErrorCode.PERMISSION_DENIED, message="无权删除此应用")

    # 清理关联对话历史（异常只记日志不阻断删除）
    try:
        delete_chat_history_fn(app_id)
    except Exception as e:
        logger.error(f"删除应用对话历史失败，应用ID: {app_id}, 错误: {str(e)}")

    app.is_delete = 1
    db.session.commit()


# ==================== 查询 ====================

def get_app_detail_svc(app_id: int) -> AppDetailResponse:
    """
    获取应用详情（含创建者简略信息）

    Args:
        app_id: 应用 ID

    Returns:
        AppDetailResponse: 包含应用 ID、应用名称、应用覆盖范围、初始化提示、创建者信息的响应模型

    Raises:
        BusinessException: 应用不存在
    """
    if not app_id or app_id <= 0:
        raise BusinessException(ErrorCode.BAD_REQUEST, message="应用ID必须为大于0的整数")

    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.APP_NOT_FOUND)

    user_info = User.query.filter_by(id=app.user_id).first()
    user_summary = UserSummaryResponse(**user_info.to_dict())
    return AppDetailResponse(**app.to_dict(user_name=user_summary.user_name, user=user_summary))


def list_apps_svc(
    user: User,
    page: int,
    per_page: int,
    app_name: Optional[str],
    code_gen_type: Optional[str],
    user_name: Optional[str],
    is_mine: bool,
    sort_field: str,
    sort_order: str,
) -> AppListResponse:
    """
    分页查询应用列表
    - 普通用户：默认只查自己的，可通过 is_mine=true 强制限定
    - 管理员：可查全部 + 按 user_name 搜索

    Args:
        user: 当前登录用户
        page: 当前页码
        per_page: 每页数量
        app_name: 应用名称模糊搜索
        code_gen_type: 代码生成类型筛选
        user_name: 用户名模糊搜索，管理员可用
        is_mine: 是否只查询当前用户的应用
        sort_field: 排序字段
        sort_order: 排序方向
    Returns:
        AppListResponse: 包含应用列表、总页数、总应用数的响应模型

    Raises:
        BusinessException: 排序字段无效或方向无效
       """
    validate_sort_params(
        sort_field, sort_order,
        allowed_fields={'id', 'app_name', 'create_time', 'update_time', 'priority'},
    )

    query = AppModel.query.filter_by(is_delete=0)

    # code_gen_type 筛选
    if code_gen_type:
        query = query.filter(AppModel.code_gen_type == code_gen_type)

    # 用户身份筛选
    if user.user_role == UserRole.ADMIN:
        # Bug 修复：原来这里写的是 AppModel.user_name（不存在的字段）
        # 管理员按 user_name 搜索 → 需要 JOIN User 表
        if user_name:
            query = query.join(User, AppModel.user_id == User.id).filter(
                User.user_name.like(f'%{user_name}%')
            )
    else:
        query = query.filter(AppModel.user_id == user.id)

    # 模糊搜索应用名称
    if app_name:
        query = query.filter(AppModel.app_name.like(f'%{app_name}%'))

    # is_mine 强制限定，管理员可能需要只查询自己的应用
    if is_mine:
        query = query.filter(AppModel.user_id == user.id)

    # 排序 + 分页
    sort_column = getattr(AppModel, sort_field)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    apps = _attach_user_name_to_apps(pagination.items)
    return AppListResponse(
        apps=apps,
        total=pagination.total,
        total_pages=pagination.pages,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
    )


def list_featured_apps_svc(page: int, per_page: int) -> AppListResponse:
    """
    分页查询精选应用（priority > 50）
    Args:
        page: 当前页码
        per_page: 每页数量
    Returns:
        AppListResponse: 包含精选应用列表、总页数、总应用数的响应模型
    Raises:
        BusinessException: 排序字段无效或方向无效
       """
    if not page or page <= 0:
        raise BusinessException(ErrorCode.BAD_REQUEST, message="页码必须为大于0的整数")
    if not per_page or per_page <= 0 or per_page > 100:
        raise BusinessException(ErrorCode.BAD_REQUEST, message="每页数量必须为大于且小于等于100的整数")
    query = AppModel.query.filter(
        AppModel.is_delete == 0,
        AppModel.priority > 50,
    ).order_by(AppModel.priority.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    apps = _attach_user_name_to_apps(pagination.items)
    return AppListResponse(
        apps=apps,
        total=pagination.total,
        total_pages=pagination.pages,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
    )


def _attach_user_name_to_apps(app_items) -> list[dict]:
    """给应用列表批量附加创建者简略信息（user + user_name）

    消除 list_apps_svc / list_featured_apps_svc 里重复的 7 行代码。
    """
    apps = [a.to_summary_dict() for a in app_items]
    user_ids = list(set(a["user_id"] for a in apps))
    user_map = {
        u.id: u.to_summary_dict()
        for u in User.query.filter(User.id.in_(user_ids)).all()
    }
    for app_dict in apps:
        user_summary = user_map.get(app_dict["user_id"])
        app_dict["user"] = user_summary
        if user_summary:
            app_dict["user_name"] = user_summary["user_name"]
    return apps


# ==================== 部署 ====================

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

    # 复制代码文件
    source_dir = os.path.join(DEFAULT_GENERATE_ROOT, f"{app.code_gen_type}_{app.id}")
    if not os.path.isdir(source_dir):
        raise BusinessException(ErrorCode.APP_NOT_FOUND, "应用代码不存在，请确认是否已生成")

    target_dir = os.path.join(DEFAULT_DEPLOY_ROOT, app.deploy_key)
    try:
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    except Exception as e:
        raise BusinessException(ErrorCode.INTERNAL_ERROR, f"部署应用失败: {str(e)}")

    app.deploy_time = datetime.utcnow()
    db.session.commit()

    # 启动 nginx（如未运行）
    if not _is_nginx_running():
        if not _start_nginx():
            raise BusinessException(ErrorCode.INTERNAL_ERROR, "启动 nginx 失败")

    return {
        "deploy_key": app.deploy_key,
        "deploy_url": f"http://localhost/{app.deploy_key}",
    }


def _is_nginx_running() -> bool:
    """检查 nginx 进程是否正在运行"""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq nginx.exe'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return 'nginx.exe' in result.stdout.lower()
    except Exception as e:
        logger.error(f"检查 nginx 进程失败: {str(e)}")
        return False


def _start_nginx() -> bool:
    """启动 nginx"""
    try:
        subprocess.Popen(
            [NGINX_PATH],
            cwd=os.path.dirname(NGINX_PATH),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
    except Exception as e:
        logger.error(f"启动 nginx 失败: {str(e)}")
        return False


# ==================== 查询辅助（供其他 Service / 路由层复用）====================

def get_app_by_deploy_key(deploy_key: str) -> AppModel | None:
    """根据 deploy_key 查询应用（含软删除过滤），不存在返回 None"""
    return AppModel.query.filter_by(deploy_key=deploy_key, is_delete=0).first()


def get_app_by_id(app_id: int) -> AppModel | None:
    """根据 ID 查询应用（含软删除过滤），不存在返回 None"""
    return AppModel.query.filter_by(id=app_id, is_delete=0).first()


def _get_app_or_raise(app_id: int) -> AppModel:
    """查询应用，不存在则抛出 BusinessException"""
    app = get_app_by_id(app_id)
    if not app:
        raise BusinessException(ErrorCode.APP_NOT_FOUND, message="应用不存在")
    return app


def get_app_creator_by_app_id(app_id: int) -> User | None:
    """根据应用 ID 查询创建者（含软删除过滤），不存在返回 None"""
    app = get_app_by_id(app_id)
    if not app:
        return None
    return User.query.filter_by(id=app.user_id, is_delete=0).first()
