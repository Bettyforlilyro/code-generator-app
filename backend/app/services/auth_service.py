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
from backend.app.services.user_service import get_user_by_id_svc


# ==================== 账号生成 ====================
def generate_user_account() -> str:
    """
    生成唯一的用户账号

    规则：时间戳后6位 + 随机4位字符

    Returns:
        唯一的用户账号字符串
    """
    timestamp_suffix = str(int(time.time() * 1000))[-6:]
    random_suffix = str(uuid.uuid4()).replace('-', '')[:4]
    return f"{timestamp_suffix}{random_suffix}"


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
    # 检查账号是否已存在
    existing_user = User.query.filter_by(user_name=req.user_name, is_delete=0).first()
    if existing_user:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "用户名已存在")

    # 创建新用户
    user_account = generate_user_account()
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

    user = get_user_by_id_svc(payload['user_id'], raise_if_not_found=False)
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
        user = get_user_by_id_svc(payload['user_id'])
        if not user:
            raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(ErrorCode.INTERNAL_ERROR, message=f"刷新Token失败: {str(e)}")

    return generate_access_token(user.id, user.user_role)


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