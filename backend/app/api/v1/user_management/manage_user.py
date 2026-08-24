from flask import request, g

from backend.app.api.v1.user_management import user_management_bp
from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.models.user import User
from backend.app.common.utils.auth import login_required, role_required
from backend.app.extensions.db_instance import db
from backend.app.schemas.requests.user_management_request import UserUpdateRequest, UserRegisterRequest
from backend.app.schemas.responses.BaseResponse import success_response, error_response


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
    req = UserUpdateRequest(**data)
    if req.user_name is not None:
        user.user_name = req.user_name
    if req.user_avatar is not None:
        user.user_avatar = req.user_avatar
    if req.user_profile is not None:
        user.user_profile = req.user_profile

    db.session.commit()

    return success_response({'message': '更新成功'})


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
    # ==================== 1. 解析并校验分页参数 ====================
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # 校验分页参数合法性
    if page < 1:
        return error_response(ErrorCode.INVALID_PARAMETER, "页码必须大于等于1")
    if per_page < 1 or per_page > 100:
        return error_response(ErrorCode.INVALID_PARAMETER, "每页数量必须在1-100之间")

    # ==================== 2. 解析筛选参数 ====================
    user_name = request.args.get('user_name')
    user_account = request.args.get('user_account')
    user_role = request.args.get('user_role')

    # ==================== 3. 解析排序参数 ====================
    sort_field = request.args.get('sort_field', 'create_time')
    sort_order = request.args.get('sort_order', 'desc')

    # 白名单校验排序字段，防止SQL注入或字段错误
    ALLOWED_SORT_FIELDS = {'id', 'user_name', 'user_account', 'create_time', 'update_time', 'user_role'}
    if sort_field not in ALLOWED_SORT_FIELDS:
        return error_response(ErrorCode.INVALID_PARAMETER, f"排序字段无效，允许的字段: {', '.join(ALLOWED_SORT_FIELDS)}")

    # 校验排序方向
    if sort_order not in ('asc', 'desc'):
        return error_response(ErrorCode.INVALID_PARAMETER, "排序方向无效，仅支持 asc 或 desc")

    # ==================== 4. 构建查询 ====================
    query = User.query.filter_by(is_delete=0)

    # 模糊搜索
    if user_name:
        query = query.filter(User.user_name.like(f'%{user_name}%'))
    if user_account:
        query = query.filter(User.user_account.like(f'%{user_account}%'))
    if user_role:
        query = query.filter(User.user_role.like(f'%{user_role}%'))

    # 排序
    sort_column = getattr(User, sort_field)
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # ==================== 5. 执行分页查询 ====================
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # ==================== 6. 构建响应数据 ====================
    users = [
        {
            'id': u.id,
            'user_account': u.user_account,
            'user_name': u.user_name,
            'user_avatar': u.user_avatar,
            'user_profile': u.user_profile,
            'user_role': u.user_role,
            'create_time': u.create_time.isoformat() if u.create_time else None
        }
        for u in pagination.items
    ]

    return success_response({
        'users': users,
        'total': pagination.total,
        'total_pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })


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
    role = json_data.get('user_role', UserRole.USER.value)

    # 检查账号是否已存在
    existing_user = User.query.filter_by(user_name=req.user_name, is_delete=0).first()
    if existing_user:
        return error_response(ErrorCode.DUPLICATE_DATA, "用户名已存在")

    # 生成账号逻辑可以复用 register.py 中的函数，或者简单处理
    import time, uuid
    timestamp_suffix = str(int(time.time() * 1000))[-6:]
    random_suffix = str(uuid.uuid4()).replace('-', '')[:4]
    user_account = f"user_{timestamp_suffix}{random_suffix}"

    new_user = User(
        user_account=user_account,
        user_name=req.user_name,
        user_role=role
    )
    new_user.set_password(req.user_password)

    db.session.add(new_user)
    db.session.commit()

    return success_response({
        'id': new_user.id,
        'user_account': new_user.user_account,
        'message': '用户创建成功'
    }, 201)


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
    user = User.query.filter_by(id=user_id, is_delete=0).first()
    if not user:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")

    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")

    data = request.get_json()
    req = UserUpdateRequest(**data)

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
    # UserUpdateRequest没有user_role参数，从request中获取是否有修改权限
    if data.get('user_role') is not None and data.get('user_role') != user.user_role:
        user.user_role = data.get('user_role')
        is_updated = True
    if is_updated:  # 降低提交次数，有更新才提交
        db.session.commit()
    return success_response({'message': '用户信息更新成功'})


@user_management_bp.route('/<int:user_id>', methods=['DELETE'])
@role_required('admin')
def delete_user_by_admin(user_id):
    """
    管理员删除用户（软删除）
    ---
    tags:
      - 管理员-用户管理
    summary: 删除用户
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
    responses:
      200:
        description: 删除成功
    """
    user = User.query.filter_by(id=user_id, is_delete=0).first()
    if not user:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, message="用户不存在")

    # 软删除：标记 is_delete 为 1
    user.is_delete = 1
    db.session.commit()
    return success_response({'message': '用户删除成功'})
