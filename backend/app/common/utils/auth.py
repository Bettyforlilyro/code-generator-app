import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, current_app, g
from backend.app.common.exceptions.error_codes import AuthenticationError, PermissionDeniedError
from backend.app.models.user import User


def generate_access_token(user_id, user_role):
    """生成短期 Access Token（15分钟）"""
    payload = {
        'type': 'access',
        'user_id': user_id,
        'user_role': user_role,
        'exp': datetime.utcnow() + timedelta(minutes=15),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    return token


def generate_refresh_token(user_id):
    """生成长期 Refresh Token（7天）"""
    payload = {
        'type': 'refresh',
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=7),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, current_app.config['REFRESH_SECRET_KEY'], algorithm='HS256')
    return token


def verify_access_token(token):
    """验证 Access Token"""
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])

        if payload.get('type') != 'access':
            raise AuthenticationError(message="无效的Token类型")

        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(message="Access Token已过期，请刷新")
    except jwt.InvalidTokenError:
        raise AuthenticationError(message="Access Token无效")


def verify_refresh_token(token):
    """验证 Refresh Token"""
    try:
        payload = jwt.decode(token, current_app.config['REFRESH_SECRET_KEY'], algorithms=['HS256'])

        if payload.get('type') != 'refresh':
            raise AuthenticationError(message="无效的Token类型")

        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(message="Refresh Token已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise AuthenticationError(message="Refresh Token无效")


def login_required(f):
    """登录验证装饰器（使用 Access Token）"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            raise AuthenticationError(message="未提供认证Token")

        if token.startswith('Bearer '):
            token = token[7:]

        payload = verify_access_token(token)
        user = User.query.filter_by(id=payload['user_id'], is_delete=0).first()

        if not user:
            raise AuthenticationError(message="用户不存在")

        g.current_user = user
        return f(*args, **kwargs)

    return decorated_function


def role_required(*roles):
    """角色权限验证装饰器，此装饰器已内置login_required"""

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not roles:
                return f(*args, **kwargs)
            if g.current_user.user_role not in roles:
                raise PermissionDeniedError(message=f"需要以下角色权限: {', '.join(roles)}")
            return f(*args, **kwargs)

        return decorated_function

    return decorator
