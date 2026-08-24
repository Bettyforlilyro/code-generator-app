from flask import request, g, after_this_request, current_app

from backend.app.api.v1.user_management import user_management_bp
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.models.user import User
from backend.app.common.utils.auth import login_required, generate_access_token, generate_refresh_token, \
    verify_refresh_token, verify_access_token
from backend.app.schemas.requests.user_management_request import UserLoginRequest
from backend.app.schemas.responses.BaseResponse import success_response, error_response
from backend.app.schemas.responses.user_management_response import UserLoginResponse


@user_management_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录接口
    ---
    tags:
      - 用户管理
    summary: 用户登录
    description: 使用用户名和密码进行登录，验证成功后返回用户信息、Access Token和Refresh Token
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_name
            - user_password
          properties:
            user_name:
              type: string
              maxLength: 256
              description: 用户昵称
              example: 张三
            user_password:
              type: string
              maxLength: 512
              description: 用户密码
              example: Password123!
    responses:
      200:
        description: ✅ 响应示例1：登录成功 - 返回用户信息和双Token
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 20000
            message:
              type: string
              example: 操作成功
            data:
              type: object
              properties:
                user_id:
                  type: integer
                  example: 1
                user_account:
                  type: string
                  example: user_123456abcd
                user_name:
                  type: string
                  example: 张三
                user_avatar:
                  type: string
                  nullable: true
                  description: 用户头像URL地址
                  example: https://example.com/avatar.jpg
                user_profile:
                  type: string
                  nullable: true
                  description: 用户简介（签名）
                  example: 请输入文本
                user_role:
                  type: string
                  example: user
                access_token:
                  type: string
                  description: 短期访问令牌（15分钟有效）
                  example: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
      400:
        description: ❌ 响应示例2：请求参数错误 - 用户名或密码为空
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40002
            message:
              type: string
              example: 用户名和密码不能为空
            data:
              type: object
              nullable: true
              example: null
      401:
        description: 🔒 响应示例3：认证失败 - 账号或密码错误
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40100
            message:
              type: string
              example: 账号或密码错误
            data:
              type: object
              nullable: true
              example: null
      500:
        description: 💥 响应示例4：服务器内部错误 - 请联系管理员
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 50000
            message:
              type: string
              example: 服务器内部错误
    """
    json_data = request.get_json()
    if not json_data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")
    user_name = json_data.get('user_name')
    pass_word = json_data.get('user_password')
    if not user_name or not pass_word:
        return error_response(ErrorCode.MISSING_PARAMETER, "用户名和密码不能为空")
    req = UserLoginRequest(**json_data)

    user = User.query.filter_by(user_name=req.user_name, is_delete=0).first()

    if not user or not user.check_password(req.user_password):
        raise BusinessException(ErrorCode.UNAUTHORIZED, message="账号或密码错误")

    # 生成双 Token
    access_token = generate_access_token(user.id, user.user_role)
    ref_token = generate_refresh_token(user.id)

    def set_refresh_cookie(resp):
        is_debug = current_app.config.get('DEBUG', False)
        resp.set_cookie(
            'refresh_token',
            ref_token,
            httponly=True,
            secure=not is_debug,    # is_debug 开发环境使用 False，生产环境使用 True
            samesite='Lax',
            max_age=7 * 24 * 60 * 60,
            path='/api/v1/user/refresh'
        )
        return resp

    # 注册回调函数设置Cookie返回给前端，主要是为了保存 Refresh Token
    after_this_request(set_refresh_cookie)

    # 创建包含 Access Token 的响应
    response_data = UserLoginResponse(
        id=user.id,
        user_account=user.user_account,
        user_name=user.user_name,
        user_avatar=user.user_avatar,
        user_profile=user.user_profile,
        user_role=user.user_role,
        token=access_token
    )

    return success_response(response_data.model_dump())


@user_management_bp.route('/login', methods=['GET'])
def get_login_user_info():
    """
    获取当前登录用户信息接口
    ---
    tags:
      - 用户管理
    summary: 获取当前登录用户信息
    description: 获取当前登录用户信息
    produces:
      - application/json
    responses:
      200:
        description: 成功获取当前登录用户信息（如果有）
    """
    # 根据当前请求信息是否携带token判断用户是否已登录，如果已登录，返回登录用户信息响应，如果未登录，返回空数据但是返回响应码都是200
    auth_token = request.headers.get('Authorization', "")
    if auth_token.startswith('Bearer '):
        auth_token = auth_token[7:]
    try:
        payload = verify_access_token(auth_token)
        user = User.query.filter_by(id=payload['user_id'], is_delete=0).first()
        if user:
            g.current_user = user
            response_data = UserLoginResponse(
                id=user.id,
                user_account=user.user_account,
                user_name=user.user_name,
                user_avatar=user.user_avatar,
                user_profile=user.user_profile,
                user_role=user.user_role,
                token=auth_token
            )
            return success_response(response_data.model_dump())
    except Exception:
        return success_response()


@user_management_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    刷新 Access Token 接口
    ---
    tags:
      - 用户管理
    summary: 刷新访问令牌
    description: 使用 Refresh Token 获取新的 Access Token，Refresh Token 通过 Cookie 传递
    produces:
      - application/json
    parameters:
      - in: cookie
        name: refresh_token
        required: true
        type: string
        description: Refresh Token（HttpOnly Cookie）
    responses:
      200:
        description: ✅ 响应示例1：刷新成功 - 返回新的 Access Token
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 20000
            message:
              type: string
              example: 操作成功
            data:
              type: object
              properties:
                access_token:
                  type: string
                  description: 新的访问令牌（15分钟有效）
                  example: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
      401:
        description: 🔒 响应示例2：Refresh Token 无效或已过期
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40100
            message:
              type: string
              example: Refresh Token已过期，请重新登录
            data:
              type: object
              nullable: true
              example: null
      500:
        description: 💥 响应示例3：服务器内部错误
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 50000
            message:
              type: string
              example: 服务器内部错误
    """
    ref_token = request.cookies.get('refresh_token')

    if not ref_token:
        raise BusinessException(ErrorCode.UNAUTHORIZED, message="未登录或登录已过期")

    try:
        payload = verify_refresh_token(ref_token)
        user = User.query.filter_by(id=payload['user_id'], is_delete=0).first()

        if not user:
            raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")

        new_access_token = generate_access_token(user.id, user.user_role)

        return success_response({
            'token': new_access_token
        })

    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(ErrorCode.INTERNAL_ERROR, message=f"刷新Token失败: {str(e)}")


@user_management_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    用户登出接口
    ---
    tags:
      - 用户管理
    summary: 用户登出
    description: 清除 Refresh Token Cookie，使 Refresh Token 失效
    produces:
      - application/json
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
        description: Access Token，格式为 "Bearer <token>"
        example: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    responses:
      200:
        description: ✅ 响应示例1：登出成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 20000
            message:
              type: string
              example: 操作成功
            data:
              type: object
              properties:
                message:
                  type: string
                  example: 登出成功
      401:
        description: 🔒 响应示例2：未登录或Token无效
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40100
            message:
              type: string
              example: 未提供认证Token
            data:
              type: object
              nullable: true
              example: null
      500:
        description: 💥 响应示例3：服务器内部错误
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 50000
            message:
              type: string
              example: 服务器内部错误
    """
    # 定义 after_request 回调函数来删除 Cookie
    def delete_refresh_cookie(response):
        response.delete_cookie('refresh_token', path='/api/v1/user/refresh')
        return response

    # 注册回调
    after_this_request(delete_refresh_cookie)

    return success_response({'message': '登出成功'})

