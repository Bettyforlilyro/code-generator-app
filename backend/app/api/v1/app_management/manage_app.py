from flask import request, g

from backend.app.api.v1.app_management import app_management_bp
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.models.app_model import AppModel

from backend.app.models.user import User
from backend.app.common.utils.auth import login_required, role_required
from backend.app.extensions.db_instance import db
from backend.app.schemas.requests.app_management_request import (
    AppCreateRequest, AppUpdateRequest, AdminAppUpdateRequest
)
from backend.app.schemas.responses.BaseResponse import success_response, error_response


# ==================== 用户接口部分 ====================

@app_management_bp.route('/', methods=['POST'])
@login_required
def create_app():
    """
    用户创建应用（需填写init_prompt）
    ---
    tags:
      - 应用管理
    summary: 创建应用
    description: 当前登录用户创建一个新的AI应用，必须提供init_prompt作为生成指令
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
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - init_prompt
          properties:
            init_prompt:
              type: string
              description: 应用初始化的用户Prompt（必填）
              example: 创建一个现代化的个人博客网站
            app_name:
              type: string
              maxLength: 256
              description: 应用名称（可选，不传则使用init_prompt前20字符）
              example: 我的博客应用
            app_coverage:
              type: string
              maxLength: 1024
              description: 应用封面图标URL（可选）
              example: https://example.com/coverage.jpg
    responses:
      200:
        description: 创建成功
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
      500:
        description: 服务器内部错误
    """
    user = g.current_user
    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")

    req = AppCreateRequest(**data)

    # 如果没有传app_name，使用init_prompt前20字符作为默认名称
    app_name = req.app_name
    if not app_name:
        app_name = req.init_prompt[:20] if len(req.init_prompt) >= 20 else req.init_prompt

    new_app = AppModel(
        app_name=app_name,
        app_coverage=req.app_coverage,
        init_prompt=req.init_prompt,
        user_id=user.id
    )

    db.session.add(new_app)
    db.session.commit()

    return success_response({
        'id': new_app.id,
        'app_name': new_app.app_name,
        'init_prompt': new_app.init_prompt,
        'user_id': new_app.user_id
    }, 201)


@app_management_bp.route('/<int:app_id>', methods=['PUT'])
@login_required
def update_app_by_user(app_id):
    """
    用户根据id修改自己创建的应用（暂时仅支持修改应用名称、封面）
    ---
    tags:
      - 应用管理
    summary: 用户更新自己的应用
    description: 当前登录用户修改自己创建的应用的名称和封面
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
      - in: path
        name: app_id
        type: integer
        required: true
        description: 应用ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            app_name:
              type: string
              minLength: 1
              maxLength: 256
              description: 应用名称（可选）
            app_coverage:
              type: string
              maxLength: 1024
              description: 应用封面图标URL（可选）
    responses:
      200:
        description: 更新成功
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足（非应用创建者）
      404:
        description: 应用不存在
    """
    user = g.current_user

    # 查找应用
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.RESOURCE_NOT_FOUND, message="应用不存在")

    # 校验权限：只有应用创建者才能修改
    if app.user_id != user.id:
        raise BusinessException(ErrorCode.FORBIDDEN, message="无权修改此应用")

    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")

    req = AppUpdateRequest(**data)

    is_updated = False

    if req.app_name is not None and req.app_name != app.app_name:
        app.app_name = req.app_name
        is_updated = True
    if req.app_coverage is not None and req.app_coverage != app.app_coverage:
        app.app_coverage = req.app_coverage
        is_updated = True

    if is_updated:
        # 手动更新edit_time
        from datetime import datetime
        app.edit_time = datetime.utcnow()
        db.session.commit()

    return success_response({'message': '应用更新成功'})


@app_management_bp.route('/<int:app_id>', methods=['DELETE'])
@login_required
def delete_app_by_user(app_id):
    """
    用户根据id删除自己的应用
    ---
    tags:
      - 应用管理
    summary: 用户删除自己的应用
    description: 当前登录用户删除自己创建的应用（软删除）
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
      - in: path
        name: app_id
        type: integer
        required: true
        description: 应用ID
    responses:
      200:
        description: 删除成功
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足（非应用创建者）
      404:
        description: 应用不存在
    """
    user = g.current_user

    # 查找应用
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.RESOURCE_NOT_FOUND, message="应用不存在")

    # 校验权限：只有应用创建者才能删除
    if app.user_id != user.id:
        raise BusinessException(ErrorCode.FORBIDDEN, message="无权删除此应用")

    # 软删除
    app.is_delete = 1
    db.session.commit()

    return success_response({'message': '应用删除成功'})


@app_management_bp.route('/<int:app_id>', methods=['GET'])
def get_app_detail(app_id):
    """
    根据id查看应用详情
    ---
    tags:
      - 应用管理
    summary: 查看应用详情
    description: 根据应用ID获取应用详细信息
    parameters:
      - in: path
        name: app_id
        type: integer
        required: true
        description: 应用ID
    responses:
      200:
        description: 返回应用详情
      404:
        description: 应用不存在
    """
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.RESOURCE_NOT_FOUND, message="应用不存在")

    return success_response(app.to_dict(include_prompt=True))


@app_management_bp.route('/my', methods=['GET'])
@login_required
def get_my_app_list():
    """
    用户分页查询自己的应用列表
    ---
    tags:
      - 应用管理
    summary: 获取我的应用列表
    description: 当前登录用户分页查询自己创建的应用列表，支持按应用名称模糊搜索
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
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
        name: app_name
        type: string
        required: false
        description: 应用名称（可选，用于模糊搜索）
      - in: query
        name: sort_field
        type: string
        required: false
        description: 排序字段（可选，默认值create_time）
        example: create_time
      - in: query
        name: sort_order
        type: string
        required: false
        description: 排序方向（可选，默认值desc，可选值asc/desc）
        example: desc
    responses:
      200:
        description: 返回应用列表
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
    """
    user = g.current_user

    # 解析并校验分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    if page < 1:
        return error_response(ErrorCode.INVALID_PARAMETER, "页码必须大于等于1")
    if per_page < 1 or per_page > 100:
        return error_response(ErrorCode.INVALID_PARAMETER, "每页数量必须在1-100之间")

    # 解析筛选参数
    app_name = request.args.get('app_name')

    # 解析排序参数
    sort_field = request.args.get('sort_field', 'create_time')
    sort_order = request.args.get('sort_order', 'desc')

    # 白名单校验排序字段
    ALLOWED_SORT_FIELDS = {'id', 'app_name', 'create_time', 'update_time', 'priority'}
    if sort_field not in ALLOWED_SORT_FIELDS:
        return error_response(ErrorCode.INVALID_PARAMETER, f"排序字段无效，允许的字段: {', '.join(ALLOWED_SORT_FIELDS)}")

    if sort_order not in ('asc', 'desc'):
        return error_response(ErrorCode.INVALID_PARAMETER, "排序方向无效，仅支持 asc 或 desc")

    # 构建查询 - 只查当前用户的应用
    query = AppModel.query.filter_by(user_id=user.id, is_delete=0)

    # 模糊搜索
    if app_name:
        query = query.filter(AppModel.app_name.like(f'%{app_name}%'))

    # 排序
    sort_column = getattr(AppModel, sort_field)
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # 执行分页查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 构建响应数据
    apps = [a.to_summary_dict() for a in pagination.items]

    return success_response({
        'apps': apps,
        'total': pagination.total,
        'total_pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })


# ==================== 管理员接口部分 ====================

@app_management_bp.route('/admin/<int:app_id>', methods=['DELETE'])
@role_required('admin')
def delete_app_by_admin(app_id):
    """
    管理员根据id删除任意应用
    ---
    tags:
      - 管理员-应用管理
    summary: 管理员删除应用
    description: 管理员根据ID删除任意应用（软删除）
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
      - in: path
        name: app_id
        type: integer
        required: true
        description: 应用ID
    responses:
      200:
        description: 删除成功
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足
      404:
        description: 应用不存在
    """
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.RESOURCE_NOT_FOUND, message="应用不存在")

    # 软删除
    app.is_delete = 1
    db.session.commit()

    return success_response({'message': '应用删除成功'})


@app_management_bp.route('/admin/<int:app_id>', methods=['PUT'])
@role_required('admin')
def update_app_by_admin(app_id):
    """
    管理员根据id更新任意应用（修改应用名称、封面、展示优先级）
    ---
    tags:
      - 管理员-应用管理
    summary: 管理员更新应用
    description: 管理员根据ID更新应用的名称、封面、展示优先级
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
      - in: path
        name: app_id
        type: integer
        required: true
        description: 应用ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            app_name:
              type: string
              minLength: 1
              maxLength: 256
              description: 应用名称（可选）
            app_coverage:
              type: string
              maxLength: 1024
              description: 应用封面图标URL（可选）
            priority:
              type: integer
              ge: 0
              description: 首页展示优先级（可选）
    responses:
      200:
        description: 更新成功
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足
      404:
        description: 应用不存在
    """
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.RESOURCE_NOT_FOUND, message="应用不存在")

    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")

    req = AdminAppUpdateRequest(**data)

    is_updated = False

    if req.app_name is not None and req.app_name != app.app_name:
        app.app_name = req.app_name
        is_updated = True
    if req.app_coverage is not None and req.app_coverage != app.app_coverage:
        app.app_coverage = req.app_coverage
        is_updated = True
    if req.priority is not None and req.priority != app.priority:
        app.priority = req.priority
        is_updated = True

    if is_updated:
        db.session.commit()

    return success_response({'message': '应用信息更新成功'})


@app_management_bp.route('/admin/list', methods=['GET'])
@role_required('admin')
def get_all_app_list():
    """
    管理员分页查询应用列表（所有应用）
    ---
    tags:
      - 管理员-应用管理
    summary: 管理员获取所有应用列表
    description: 管理员分页查询所有应用信息，支持按应用名称、创建用户ID进行模糊搜索；支持排序
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
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
        name: app_name
        type: string
        required: false
        description: 应用名称（可选，用于模糊搜索）
      - in: query
        name: user_id
        type: integer
        required: false
        description: 创建用户ID（可选）
      - in: query
        name: sort_field
        type: string
        required: false
        description: 排序字段（可选，默认值create_time）
        example: create_time
      - in: query
        name: sort_order
        type: string
        required: false
        description: 排序方向（可选，默认值desc，可选值asc/desc）
        example: desc
    responses:
      200:
        description: 返回应用列表
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足
    """
    # 解析并校验分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    if page < 1:
        return error_response(ErrorCode.INVALID_PARAMETER, "页码必须大于等于1")
    if per_page < 1 or per_page > 100:
        return error_response(ErrorCode.INVALID_PARAMETER, "每页数量必须在1-100之间")

    # 解析筛选参数
    app_name = request.args.get('app_name')
    user_id = request.args.get('user_id', type=int)

    # 解析排序参数
    sort_field = request.args.get('sort_field', 'create_time')
    sort_order = request.args.get('sort_order', 'desc')

    # 白名单校验排序字段
    ALLOWED_SORT_FIELDS = {'id', 'app_name', 'create_time', 'update_time', 'priority', 'user_id'}
    if sort_field not in ALLOWED_SORT_FIELDS:
        return error_response(ErrorCode.INVALID_PARAMETER, f"排序字段无效，允许的字段: {', '.join(ALLOWED_SORT_FIELDS)}")

    if sort_order not in ('asc', 'desc'):
        return error_response(ErrorCode.INVALID_PARAMETER, "排序方向无效，仅支持 asc 或 desc")

    # 构建查询
    query = AppModel.query.filter_by(is_delete=0)

    # 模糊搜索
    if app_name:
        query = query.filter(AppModel.app_name.like(f'%{app_name}%'))
    if user_id:
        query = query.filter(AppModel.user_id == user_id)

    # 排序
    sort_column = getattr(AppModel, sort_field)
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # 执行分页查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 构建响应数据
    apps = [a.to_summary_dict() for a in pagination.items]

    return success_response({
        'apps': apps,
        'total': pagination.total,
        'total_pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })
