from flask import request, g

from backend.app.api.v1.user_management import user_management_bp
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import login_required, role_required
from backend.app.schemas.requests.user_management_request import UserUpdateRequest, UserRegisterRequest
from backend.app.schemas.responses.BaseResponse import success_response, error_response
from backend.app.services.user_service import (
    update_current_user_info,
    admin_get_user_list,
    admin_create_user,
    admin_update_user,
    admin_delete_user,
)


@user_management_bp.route('/', methods=['PUT'])
@login_required
def update_user_self_info():
    """
    更新用户信息接口
    ---
    tags:
      - 用户管理
    summary: 更新用户自己的信息
    description: 更新当前登录用户的昵称、头像或个人简介，所有字段均为可选
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
        description: JWT Token，格式为 "Bearer <token>"
        example: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            user_name:
              type: string
              minLength: 1
              maxLength: 50
              description: 用户昵称（可选）
              example: 李四
            user_avatar:
              type: string
              maxLength: 1024
              description: 用户头像URL（可选）
              example: https://example.com/new-avatar.jpg
            user_profile:
              type: string
              maxLength: 512
              description: 用户简介（可选）
              example: 这是我的新简介
    responses:
      200:
        description: ✅ 响应示例1：更新成功
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
                  example: 更新成功
      400:
        description: ❌ 响应示例2：请求参数错误 - 字段长度超出限制
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40003
            message:
              type: string
              example: 参数值无效
            data:
              type: object
              nullable: true
              example: null
      401:
        description: 🔒 响应示例3：未登录或Token无效
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
        description: 💥 响应示例4：服务器内部错误
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
    user = g.current_user
    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")

    try:
        req = UserUpdateRequest(**data)
        update_current_user_info(user, req)
        return success_response({'message': '更新成功'})
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)


# ==================== 管理员接口部分 ====================

@user_management_bp.route('/', methods=['GET'])
@role_required('admin')
def get_user_list_page():
    """
    获取用户分页列表（仅管理员）
    ---
    tags:
      - 管理员-用户管理
    summary: 获取用户列表
    description: 分页查询所有普通用户信息，可以支持通过：用户账户user_account、用户名user_name、用户角色user_role 进行模糊搜索；同时可以指定查询分页参数、排序字段和排序方向（默认按创建时间降序）
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
        description: 页码，可选，默认值1
      - in: query
        name: per_page
        type: integer
        default: 10
        description: 每页数量，可选，默认值10
      - in: query
        name: user_name
        type: string
        required: false
        description: 用户名（可选，用于模糊搜索）
      - in: query
        name: user_account
        type: string
        required: false
        description: 用户账户（可选，用于模糊搜索）
      - in: query
        name: user_role
        type: string
        required: false
        description: 用户角色（可选，用于模糊搜索）
        example: user
      - in: query
        name: sort_field
        type: string
        required: false
        description: 排序字段（可选，默认值create_time降序）
        example: create_time
      - in: query
        name: sort_order
        type: string
        required: false
        description: 排序方向（可选，默认值desc，可选值asc/desc）
        example: desc
    responses:
      200:
        description: 成功返回用户列表
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
                users:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
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
                        example: https://example.com/avatar.jpg
                      user_profile:
                        type: string
                        nullable: true
                        example: 这是用户简介
                      user_role:
                        type: string
                        example: user
                      create_time:
                        type: string
                        example: "2024-01-15T10:30:00"
                total:
                  type: integer
                  example: 100
                page:
                  type: integer
                  example: 1
                per_page:
                  type: integer
                  example: 10
                total_pages:
                  type: integer
                  example: 10
                has_next:
                  type: boolean
                  example: true
                has_prev:
                  type: boolean
                  example: false
      400:
        description: 请求参数错误
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40003
            message:
              type: string
              example: 参数值无效
            data:
              type: object
              nullable: true
              example: null
      401:
        description: 未登录或Token无效
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
      403:
        description: 权限不足
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40300
            message:
              type: string
              example: 没有权限访问
            data:
              type: object
              nullable: true
              example: null
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 50000
            message:
              type: string
              example: 服务器内部错误
            data:
              type: object
              nullable: true
              example: null
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if page < 1:
        return error_response(ErrorCode.INVALID_PARAMETER, "页码必须大于等于1")
    if per_page < 1 or per_page > 100:
        return error_response(ErrorCode.INVALID_PARAMETER, "每页数量必须在1-100之间")

    user_name = request.args.get('user_name')
    user_account = request.args.get('user_account')
    user_role = request.args.get('user_role')
    sort_field = request.args.get('sort_field', 'create_time')
    sort_order = request.args.get('sort_order', 'desc')

    try:
        result = admin_get_user_list(
            page=page, per_page=per_page,
            user_name=user_name, user_account=user_account, user_role=user_role,
            sort_field=sort_field, sort_order=sort_order,
        )
        return success_response(result)
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)


@user_management_bp.route('/', methods=['POST'])
@role_required('admin')
def create_user_by_admin():
    """
    管理员创建新用户（并非普通用户注册，可以创建管理员权限账户）
    ---
    tags:
      - 管理员-用户管理
    summary: 创建用户
    description: 管理员直接创建账号，可以创建管理员账号，也可以普通账号
    responses:
      200:
        description: 创建成功
    """
    json_data = request.get_json()
    if not json_data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")

    try:
        req = UserRegisterRequest(**json_data)
    except Exception as e:
        return error_response(ErrorCode.INVALID_PARAMETER, str(e))

    role = json_data.get('user_role', 'user')

    try:
        result = admin_create_user(req, role)
        return success_response(result, 201)
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)


@user_management_bp.route('/<int:user_id>', methods=['PUT'])
@role_required('admin')
def update_user_by_admin(user_id):
    """
    管理员修改任意用户信息
    ---
    tags:
      - 管理员-用户管理
    summary: 修改用户信息，可以修改用户名、头像、简介、角色权限
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
    responses:
      200:
        description: 修改成功
    """
    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")

    try:
        req = UserUpdateRequest(**data)
        admin_update_user(user_id, req, data)
        return success_response({'message': '用户信息更新成功'})
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)


@user_management_bp.route('/<int:user_id>', methods=['DELETE'])
@role_required('admin')
def delete_user_by_admin(user_id):
    try:
        admin_delete_user(user_id)
        return success_response({'message': '用户删除成功'})
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)