"""
用户 Service 层

集中封装 User 模型的所有业务逻辑和数据库操作。
"""
import time
import uuid

from flask import current_app
from flask.ctx import after_this_request

from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import (
    generate_access_token,
    generate_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from backend.app.common.utils.get_random_picture import get_random_avatar
from backend.app.extensions.db_instance import db
from backend.app.models.user import User
from backend.app.schemas.requests.user_management_request import UserRegisterRequest
from backend.app.schemas.responses.user_management_response import (
    UserLoginResponse,
    UserRegisterResponse,
)
from backend.app.services.common import validate_sort_params


# ==================== 用户信息维护 ====================

def get_user_by_id_svc(user_id: int, raise_if_not_found: bool = True) -> User | None:
    """根据用户 ID 获取用户信息（统一的软删除过滤查询）

    Args:
        user_id: 用户 ID
        raise_if_not_found: 不存在时是否抛异常，默认 True

    Raises:
        BusinessException: 用户不存在（raise_if_not_found=True 时）
    """
    user = User.query.filter_by(id=user_id, is_delete=0).first()
    if not user and raise_if_not_found:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")
    return user


def update_current_user_info(user: User, req) -> None:
    """更新当前登录用户的昵称、头像、简介"""
    is_updated = False
    if req.user_name is not None and req.user_name != user.user_name:
        user.user_name = req.user_name
        is_updated = True
    if req.user_avatar is not None and req.user_avatar != user.user_avatar:
        user.user_avatar = req.user_avatar
        is_updated = True
    if req.user_profile is not None and req.user_profile != user.user_profile:
        user.user_profile = req.user_profile
        is_updated = True
    if is_updated:
        db.session.commit()


def admin_get_user_list(
    page: int,
    per_page: int,
    user_name: str | None,
    user_account: str | None,
    user_role: str | None,
    sort_field: str,
    sort_order: str,
) -> dict:
    """
    管理员分页查询用户列表

    Args:
        page: 当前页码
        per_page: 每页显示用户数量
        user_name: 用户昵称或邮箱
        user_account: 用户账号
        user_role: 用户角色
        sort_field: 排序字段
        sort_order: 排序方向（asc 或 desc）

    Returns:
        dict: 包含用户列表、总用户数、总页数、是否有下一页、是否有上一页的字典

    Raises:
        BusinessException: 排序字段无效或排序方向无效
    """
    validate_sort_params(
        sort_field, sort_order,
        allowed_fields={'id', 'user_name', 'user_account', 'create_time', 'update_time', 'user_role'},
    )

    query = User.query.filter_by(is_delete=0)
    if user_name:
        query = query.filter(User.user_name.like(f'%{user_name}%'))
    if user_account:
        query = query.filter(User.user_account.like(f'%{user_account}%'))
    if user_role:
        query = query.filter(User.user_role.like(f'%{user_role}%'))

    sort_column = getattr(User, sort_field)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = [
        {
            'id': u.id,
            'user_account': u.user_account,
            'user_name': u.user_name,
            'user_avatar': u.user_avatar,
            'user_profile': u.user_profile,
            'user_role': u.user_role,
            'create_time': u.create_time.isoformat() if u.create_time else None,
        }
        for u in pagination.items
    ]
    return {
        'users': users,
        'total': pagination.total,
        'total_pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    }


def admin_create_user(req: UserRegisterRequest, role: UserRole = UserRole.USER.value) -> dict:
    """
    管理员创建用户

    Args:
        req: 用户注册请求
        role: 用户角色（默认 USER）

    Returns:
        dict: 包含用户 ID、用户账号、成功消息的字典

    Raises:
        BusinessException: 用户名已存在
    """
    # 检查用户名是否已存在
    existing_user = User.query.filter_by(user_name=req.user_name, is_delete=0).first()
    if existing_user:
        raise BusinessException(ErrorCode.USER_NAME_EXISTS, message="用户名已存在，请选择其他用户名")

    user_account = generate_user_account(req.user_name)
    new_user = User(
        user_account=user_account,
        user_name=req.user_name,
        user_role=role,
    )
    new_user.set_password(req.user_password)

    db.session.add(new_user)
    db.session.commit()

    return {
        'id': new_user.id,
        'user_account': new_user.user_account,
        'message': '用户创建成功',
    }


def admin_update_user(user_id: int, req, user_role: UserRole | None = None) -> None:
    """
    管理员修改任意用户信息

    Args:
        user_id: 用户 ID
        req: 用户更新请求
        user_role: 用户角色，可以为None表示不修改角色

    Raises:
        BusinessException: 用户不存在
    """
    user = get_user_by_id_svc(user_id)

    is_updated = False
    if req.user_name is not None and req.user_name != user.user_name:
        user.user_name = req.user_name
        is_updated = True
    if req.user_avatar is not None and req.user_avatar != user.user_avatar:
        user.user_avatar = req.user_avatar
        is_updated = True
    if req.user_profile is not None and req.user_profile != user.user_profile:
        user.user_profile = req.user_profile
        is_updated = True
    # 管理员可以改角色（UserUpdateRequest 里没有 role，从原始 data 中取）
    if user_role is not None and user_role != user.user_role:
        user.user_role = user_role
        is_updated = True

    if is_updated:
        db.session.commit()


def admin_delete_user(user_id: int) -> None:
    """管理员软删除用户"""
    user = get_user_by_id_svc(user_id)
    user.is_delete = 1
    db.session.commit()
