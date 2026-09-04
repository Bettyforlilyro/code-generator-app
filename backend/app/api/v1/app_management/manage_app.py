from flask import request, g

from backend.app.api.v1.app_management import app_management_bp
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import login_required
from backend.app.common.utils.request_helpers import parse_json_body, parse_pagination_args
from backend.app.schemas.requests.app_management_request import (
    AppCreateRequest, AppUpdateRequest, AdminAppUpdateRequest
)
from backend.app.schemas.responses.BaseResponse import success_response, error_response
from backend.app.services.app_service import create_app_svc, update_app_svc, delete_app_svc, get_app_detail_svc, \
    list_apps_svc, list_featured_apps_svc, deploy_app_svc, get_app_by_id
from backend.app.services.chat_history_service import delete_chat_history_by_app_id


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
              description: 应用名称（可选，不传则使用由AI总结生成）
              example: 我的博客应用
            app_coverage:
              type: string
              maxLength: 1024
              description: 应用封面图标URL（可选）
              example: https://example.com/coverage.jpg
            code_gen_type:
              type: string
              description: 应用代码文件类型（可选）
              example: html
              enum: ['html', 'multi_file']
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
    data = parse_json_body()
    if 'init_prompt' not in data:
        return error_response(ErrorCode.MISSING_PARAMETER, "init_prompt不能为空")

    req = AppCreateRequest(**data)
    result = create_app_svc(user.id, req)
    return success_response(result, 201)


@app_management_bp.route('/<int:app_id>', methods=['PUT'])
@login_required
def update_app(app_id):
    """
    用户根据id修改自己创建的应用（暂时仅支持修改应用名称、封面），管理员可以修改应用优先级
    ---
    tags:
      - 应用管理
    summary: 更新应用
    description: 当前登录用户修改自己创建的应用的名称和封面，管理员可以修改应用优先级
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
              example: https://example.com/coverage.jpg
            priority:
              type: integer
              description: 首页展示优先级（可选，值越大越靠前，仅管理员可修改，非管理员携带此参数会被忽视）
              example: 10
    responses:
      200:
        description: 更新成功
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足（非应用创建者）
      405:
        description: 应用不存在
    """
    user = g.current_user
    data = parse_json_body()

    is_admin = user.user_role == 'admin'
    req = AdminAppUpdateRequest(**data) if is_admin else AppUpdateRequest(**data)
    update_app_svc(app_id, user, req)
    return success_response({'message': '应用更新成功'})


@app_management_bp.route('/<int:app_id>', methods=['DELETE'])
@login_required
def delete_app(app_id):
    """
    删除应用，非管理员只能删除自己的应用
    ---
    tags:
      - 应用管理
    summary: 删除应用
    description: 管理员可以删除任意应用，非管理员只能删除自己的应用
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

    delete_app_svc(app_id, user, delete_chat_history_by_app_id)
    return success_response({'message': '应用删除成功'})


@app_management_bp.route('/<int:app_id>', methods=['GET'])
def get_app_detail(app_id):
    """
    根据id查看应用详情，无需登录
    ---
    tags:
      - 应用管理
    summary: 查看应用详情（无需登录）
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
    if not app_id or app_id <= 0:
        raise BusinessException(ErrorCode.BAD_REQUEST, message="应用ID必须为大于0的整数")
    app = get_app_by_id(app_id)
    if not app:
        raise BusinessException(ErrorCode.APP_NOT_FOUND)
    return success_response(get_app_detail_svc(app_id))


@app_management_bp.route('/list', methods=['GET'])
@login_required
def get_app_list():
    """
    用户分页查询应用列表
    ---
    tags:
      - 应用管理
    summary: 获取应用列表（管理员查询所有应用，普通用户查询自己的应用）
    description: 普通用户分页查询自己创建的应用列表，可按应用名称模糊搜索；管理员分页查询所有应用信息，可按应用名称、创建用户名搜索
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
        name: is_mine
        type: boolean
        default: false
        description: 是否仅查询自己的应用，可选，默认值false
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
        name: code_gen_type
        type: string
        required: false
        description: 生成类型（可选，用于模糊搜索）
      - in: query
        name: user_name
        type: string
        required: false
        description: 创建用户名（可选，用于根据user_name搜索，仅管理员可使用）
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
    page, per_page = parse_pagination_args()

    # 解析筛选参数
    app_name = request.args.get('app_name')

    # 解析排序参数
    sort_field = request.args.get('sort_field', 'create_time')
    sort_order = request.args.get('sort_order', 'desc')

    code_gen_type = request.args.get('code_gen_type', None)

    user_name = request.args.get('user_name', None)
    is_mine = request.args.get('is_mine', False, type=bool)

    app_list = list_apps_svc(
        user=user,
        page=page,
        per_page=per_page,
        app_name=app_name,
        code_gen_type=code_gen_type,
        user_name=user_name,
        is_mine=is_mine,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    return success_response(app_list)


@app_management_bp.route('/good/list', methods=['GET'])
def get_featured_app_list():
    """
    分页查询精选应用列表，无需登录
    ---
    tags:
      - 应用管理
    summary: 获取精选应用列表，精选应用（priority>50）展示按照优先级排序，优先级高的先展示
    description:
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
    responses:
      200:
        description: 返回应用列表
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
    """

    # 解析并校验分页参数
    page, per_page = parse_pagination_args()

    app_list = list_featured_apps_svc(page, per_page)
    return success_response(app_list)


@app_management_bp.route('/deploy', methods=['POST'])
@login_required
def deploy_app():
    """
    部署应用，需要登录
    ---
    tags:
      - 应用管理
    summary: 部署应用，需要登录
    description: 目前所谓的部署仅仅是将后端生成的代码文件保存到指定目录，前端可以通过返回的链接访问部署后的应用（后端需要启动相关nginx服务并完成相关配置）
    return: 部署结果和部署后访问链接
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
      - in: body
        name: app_id
        type: integer
        description: 应用ID
        required: true
    responses:
      200:
        description: 返回部署结果和部署后访问链接
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
    """
    user = g.current_user
    deploy_request = request.get_json()
    if not deploy_request or 'app_id' not in deploy_request:
        return error_response(ErrorCode.INVALID_PARAMETER, "请求参数错误")
    app_id = deploy_request.get('app_id')

    return success_response(deploy_app_svc(app_id, user.id))
