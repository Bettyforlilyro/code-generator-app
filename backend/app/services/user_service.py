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


# ==================== 账号生成 ====================

def generate_user_account(user_name: str) -> str:
    """
    生成唯一的用户账号

    规则：user_ + 时间戳后6位 + 随机4位字符

    Args:
        user_name: 用户昵称（可用于调试日志，但不直接用于账号生成）

    Returns:
        唯一的用户账号字符串
    """
    timestamp_suffix = str(int(time.time() * 1000))[-6:]
    random_suffix = str(uuid.uuid4()).replace('-', '')[:4]
    return f"user_{timestamp_suffix}{random_suffix}"


# ==================== 注册 & 登录 ====================

def register_user_svc(req: UserRegisterRequest) -> UserRegisterResponse:
    """
    用户注册：校验 → 创建用户 → 自动登录返回 Token

    Args:
        req: 用户注册请求数据

    Returns:
        UserRegisterResponse: 用户注册响应数据

    Raises:
        BusinessException: 用户名已存在等业务异常
    """
    # 2. 检查账号是否已存在
    existing_user = User.query.filter_by(user_name=req.user_name, is_delete=0).first()
    if existing_user:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "用户名已存在")

    # 3. 创建新用户
    user_account = generate_user_account(req.user_name)
    user_avatar = get_random_avatar()

    new_user = User(
        user_account=user_account,
        user_name=req.user_name,
        user_avatar=user_avatar,
        user_role=UserRole.USER.value,
    )
    new_user.set_password(req.user_password)

    db.session.add(new_user)
    db.session.commit()

    # 4. 自动登录生成双 Token
    access_token = generate_access_token(new_user.id, new_user.user_role)
    ref_token = generate_refresh_token(new_user.id)
    _set_refresh_token_cookie(ref_token)

    return UserRegisterResponse(
        id=new_user.id,
        user_account=new_user.user_account,
        user_name=new_user.user_name,
        user_role=new_user.user_role,
        token=access_token,
    )


def login_user(user_name: str, user_password: str) -> UserLoginResponse:
    """
    用户登录：验证账号密码 → 返回 Token

    Args:
        user_name: 用户昵称或邮箱
        user_password: 用户密码

    Returns:
        UserLoginResponse: 用户登录响应数据

    Raises:
        BusinessException: 账号或密码错误
    """
    user = User.query.filter_by(user_name=user_name, is_delete=0).first()

    if not user or not user.check_password(user_password):
        raise BusinessException(ErrorCode.UNAUTHORIZED, message="账号或密码错误")

    access_token = generate_access_token(user.id, user.user_role)
    ref_token = generate_refresh_token(user.id)
    _set_refresh_token_cookie(ref_token)

    return UserLoginResponse(
        id=user.id,
        user_account=user.user_account,
        user_name=user.user_name,
        user_avatar=user.user_avatar,
        user_profile=user.user_profile,
        user_role=user.user_role,
        token=access_token,
    )


def get_login_user_info_svc(auth_token: str) -> UserLoginResponse | None:
    """
    根据 Authorization Header 获取当前登录用户信息

    Args:
        auth_token: 包含用户信息的 access token

    Returns:
        UserLoginResponse 或 None（未登录时）

    Raises:
        BusinessException: Token 无效或用户不存在

    """
    if auth_token.startswith('Bearer '):
        auth_token = auth_token[7:]
    if not auth_token:
        return None

    try:
        payload = verify_access_token(auth_token)
    except Exception:
        return None

    user = User.query.filter_by(id=payload['user_id'], is_delete=0).first()
    if not user:
        return None

    return UserLoginResponse(
        id=user.id,
        user_account=user.user_account,
        user_name=user.user_name,
        user_avatar=user.user_avatar,
        user_profile=user.user_profile,
        user_role=user.user_role,
        token=auth_token,
    )


def refresh_access_token_svc(refresh_token_str: str) -> str:
    """
    使用 Refresh Token 刷新 Access Token

    Args:
        refresh_token_str: 刷新 access token 用到的 refresh token

    Returns:
        str: 刷新后的 Access Token

    Raises:
        BusinessException: Token 无效或用户不存在
    """
    if not refresh_token_str:
        raise BusinessException(ErrorCode.UNAUTHORIZED, message="未登录或登录已过期")

    try:
        payload = verify_refresh_token(refresh_token_str)
        user = User.query.filter_by(id=payload['user_id'], is_delete=0).first()
        if not user:
            raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(ErrorCode.INTERNAL_ERROR, message=f"刷新Token失败: {str(e)}")

    return generate_access_token(user.id, user.user_role)


# ==================== 用户信息维护 ====================

def get_user_by_id(user_id: int) -> User:
    """根据用户 ID 获取用户信息"""
    user = User.query.filter_by(id=user_id, is_delete=0).first()
    if not user:
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
    ALLOWED_SORT_FIELDS = {'id', 'user_name', 'user_account', 'create_time', 'update_time', 'user_role'}
    if sort_field not in ALLOWED_SORT_FIELDS:
        raise BusinessException(ErrorCode.INVALID_PARAMETER,
                                f"排序字段无效，允许的字段: {', '.join(ALLOWED_SORT_FIELDS)}")
    if sort_order not in ('asc', 'desc'):
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "排序方向无效，仅支持 asc 或 desc")

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
        raise BusinessException(ErrorCode.DUPLICATE_DATA, "用户名已存在")

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
    user = User.query.filter_by(id=user_id, is_delete=0).first()
    if not user:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")

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
    user = User.query.filter_by(id=user_id, is_delete=0).first()
    if not user:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")
    user.is_delete = 1
    db.session.commit()


# ==================== 内部辅助 ====================

def _set_refresh_token_cookie(ref_token: str) -> None:
    """注册 after_request 回调设置 Refresh Token Cookie"""

    def _set_cookie(resp):
        is_debug = current_app.config.get('DEBUG', False)
        resp.set_cookie(
            'refresh_token',
            ref_token,
            httponly=True,
            secure=not is_debug,
            samesite='Lax',
            max_age=7 * 24 * 60 * 60,
            path='/api/v1/user/refresh',
        )
        return resp

    after_this_request(_set_cookie)


def clear_refresh_token_cookie() -> None:
    """注册 after_request 回调清除 Refresh Token Cookie（登出用）"""

    def _delete_cookie(response):
        response.delete_cookie('refresh_token', path='/api/v1/user/refresh')
        return response

    after_this_request(_delete_cookie)
