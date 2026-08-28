import os.path
import shutil
import subprocess
from datetime import datetime

from flask import request, g

from backend.app.api.v1.app_management import app_management_bp
from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT, DEFAULT_DEPLOY_ROOT, NGINX_PATH
from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import login_required
from backend.app.extensions.db_instance import db
from backend.app.models.app_model import AppModel
from backend.app.models.user import User
from backend.app.schemas.requests.app_management_request import (
    AppCreateRequest, AppUpdateRequest, AdminAppUpdateRequest
)
from backend.app.schemas.responses.BaseResponse import success_response, error_response
from backend.app.schemas.responses.app_management_response import AppDetailResponse, AppListResponse, AppCreateResponse
from backend.app.schemas.responses.user_management_response import UserSummaryResponse


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
    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")
    if 'init_prompt' not in data:
        return error_response(ErrorCode.MISSING_PARAMETER, "init_prompt不能为空")

    req = AppCreateRequest(**data)

    # TODO 如果没有传app_name，使用init_prompt前20字符作为默认名称或者AI总结生成？后续再决定如何命名
    app_name = req.app_name if req.app_name else req.init_prompt[:20]

    new_app = AppModel(
        app_name=app_name,
        code_gen_type=req.code_gen_type,
        app_coverage=req.app_coverage,
        init_prompt=req.init_prompt,
        user_id=user.id
    )

    db.session.add(new_app)
    db.session.commit()
    app_info = AppCreateResponse(**new_app.to_dict())

    return success_response(app_info, 201)


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
    # 检查应用是否存在
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在")
    is_admin = user.user_role == UserRole.ADMIN
    # 权限校验：非管理员只能修改自己的应用
    if not is_admin and app.user_id != user.id:
        return error_response(ErrorCode.PERMISSION_DENIED, "无权修改此应用")
    data = request.get_json()
    if not data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")
    # 管理员使用AdminAppUpdateRequest（支持priority），普通用户使用AppUpdateRequest
    req = AdminAppUpdateRequest(**data) if is_admin else AppUpdateRequest(**data)
    is_updated = False
    if req.app_name is not None and req.app_name != app.app_name:
        is_updated = True
    if req.app_coverage is not None and req.app_coverage != app.app_coverage:
        app.app_coverage = req.app_coverage
        is_updated = True
    # 仅管理员可修改priority
    if is_admin and req.priority is not None and req.priority != app.priority:
        app.priority = req.priority
        is_updated = True
    if is_updated:
        app.edit_time = datetime.utcnow()
        db.session.commit()
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

    # 查找应用
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.RESOURCE_NOT_FOUND, message="应用不存在")

    # 校验权限：管理员可以删除任意应用，非管理员只能删除自己的应用
    if not user.user_role == UserRole.ADMIN and app.user_id != user.id:
        raise BusinessException(ErrorCode.PERMISSION_DENIED, message="无权删除此应用")

    # 软删除
    app.is_delete = 1
    db.session.commit()

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
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        raise BusinessException(ErrorCode.APP_NOT_FOUND)
    if not app_id or app_id <= 0:
        raise BusinessException(ErrorCode.BAD_REQUEST, message="应用ID必须为大于0的整数")
    # 应该返回应用详情，包含应用创建者简略信息
    user_id = app.user_id
    user_info = User.query.filter_by(id=user_id).first()
    user = UserSummaryResponse(**user_info.to_dict())

    app_detail = AppDetailResponse(**app.to_dict(user_name=user.user_name), user=user)

    return success_response(app_detail)


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

    # 构建查询
    query = AppModel.query.filter_by(is_delete=0)
    if user.user_role == UserRole.ADMIN:
        # 管理员情况下可以根据user_name搜索，这个user_name是请求携带的参数而非current_user
        user_name = request.args.get('user_name')
        if user_name:
            query = query.filter(AppModel.user_name == user_name)
    else:   # 普通用户情况下只能查询自己创建的应用
        query = query.filter(AppModel.user_name == user.user_name)

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
    # 如果是管理员，需要返回user_name显示
    apps = [a.to_summary_dict() for a in pagination.items]
    if user.user_role == UserRole.ADMIN:
        user_ids = list(set(a["user_id"] for a in apps))
        user_map = {u.id: u.user_name for u in User.query.filter(User.id.in_(user_ids)).all()}
        for app in apps:
            app["user_name"] = user_map.get(app["user_id"], '')
    app_list = AppListResponse(
        apps=apps,
        total=pagination.total,
        total_pages=pagination.pages,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev
    )

    return success_response(app_list)


@app_management_bp.route('/good/list', methods=['GET'])
def get_good_app_list():
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
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if page < 1:
        return error_response(ErrorCode.INVALID_PARAMETER, "页码必须大于等于1")
    if per_page < 1 or per_page > 100:
        return error_response(ErrorCode.INVALID_PARAMETER, "每页数量必须在1-100之间")

    # 构建查询，priority>50才是精选应用，并且按照priority降序排序
    query = AppModel.query.filter(AppModel.is_delete == 0, AppModel.priority > 50).order_by(AppModel.priority.desc())

    # 执行分页查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 构建响应数据
    apps = [a.to_summary_dict() for a in pagination.items]
    user_ids = list(set(a["user_id"] for a in apps))
    user_map = {u.id: u.user_name for u in User.query.filter(User.id.in_(user_ids)).all()}
    for app in apps:
        app["user_name"] = user_map.get(app["user_id"], '')
    app_list = AppListResponse(
        apps=apps,
        total=pagination.total,
        total_pages=pagination.pages,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev
    )

    return success_response(app_list)


def generate_deploy_key():
    """
    生成唯一的部署键，6位随机大小写字母或数字组合
    """
    import random
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


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
    # 校验应用是否存在
    app = AppModel.query.filter(AppModel.id == app_id, AppModel.is_delete == 0).first()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在")
    # 仅本人可以部署
    if app.user_id != user.id:
        return error_response(ErrorCode.FORBIDDEN, "没有权限部署该应用")
    if not app.code_gen_type:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用实际未生成，请确认是否已生成")
    # 检查是否已经存在deploy_key，如果存在，也能重新覆盖式部署，如果不存在，重新生成deploy_key并保存到数据库
    if not app.deploy_key:
        app.deploy_key = generate_deploy_key()

    # 目前所谓的部署仅仅是将后端生成的代码文件保存到指定目录
    # TODO 后续可以根据实际情况，添加其他部署逻辑，比如调用其他服务部署应用等
    # 构建部署目录并复制代码文件
    source_dir = os.path.join(DEFAULT_GENERATE_ROOT, app.code_gen_type + '_' + str(app.id))
    if not os.path.exists(source_dir) or not os.path.isdir(source_dir):
        return error_response(ErrorCode.APP_NOT_FOUND, "应用代码不存在，请确认是否已生成")
    target_dir = os.path.join(DEFAULT_DEPLOY_ROOT, app.deploy_key)
    # 复制代码文件到部署目录
    try:
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    except Exception as e:
        raise BusinessException(ErrorCode.INTERNAL_ERROR, f"部署应用失败: {str(e)}")
    # 更新应用部署信息
    app.deploy_time = datetime.now()
    db.session.commit()
    # 查看当前系统是否已经启动nginx进程，如果不存在需要启动nginx
    if not is_nginx_running():
        if not start_nginx():
            raise BusinessException(ErrorCode.INTERNAL_ERROR, "启动 nginx 失败")
    # 暂时仅支持在localhost访问，后续可以根据实际情况，添加其他访问方式
    deploy_url = f"http://localhost/{app.deploy_key}"
    return success_response({"deploy_key": app.deploy_key, "deploy_url": deploy_url})


def is_nginx_running():
    """检查 nginx 进程是否正在运行"""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq nginx.exe'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        # tasklist 输出中包含 "nginx.exe" 字符串即表示正在运行
        return 'nginx.exe' in result.stdout.lower()
    except Exception as e:
        import logging
        logging.error(f"检查 nginx 进程失败: {str(e)}")
        return False


def start_nginx():
    """启动 nginx"""
    try:
        subprocess.Popen(
            [NGINX_PATH],
            cwd=os.path.dirname(NGINX_PATH),  # nginx 启动需要在其安装目录下
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return True
    except Exception as e:
        import logging
        logging.error(f"启动 nginx 失败: {str(e)}")
        return False
