from datetime import datetime

from flask import request, g

from backend.app.api.v1.app_management import app_management_bp
from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import login_required
from backend.app.common.utils.request_helpers import parse_pagination_args
from backend.app.schemas.responses.BaseResponse import success_response
from backend.app.services.app_service import get_app_by_id
from backend.app.services.chat_history_service import list_chat_history


@app_management_bp.route('/<string:app_id>/chat_history', methods=['GET'])
@login_required
def get_chat_history(app_id: str):
    """
    获取应用对话历史记录
    ---
    tags:
      - 对话历史
    summary: 分页获取指定应用的对话历史（需登录，管理员或应用创建者可访问）
    description: 管理员或应用创建者可分页查询该应用下的 AI 对话历史记录，支持按时间排序
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
        description: JWT Token，格式为 "Bearer <token>"
      - in: path
        name: app_id
        required: true
        type: string
        description: 应用ID
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
        name: sort_order
        type: string
        default: asc
        description: 排序方向，可选，默认值asc（按创建时间从早到晚），可选值 asc/desc
      - in: query
        name: last_create_time
        type: string
        description: 上一次分页返回的最后一条记录的创建时间（可选，格式为 YYYY&mm&dd&HH&MM&SS，用于滚动加载）
    responses:
      200:
        description: 返回对话历史分页列表
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足（非管理员且非应用创建者）
      404:
        description: 应用不存在
    """
    user = g.current_user
    page, per_page = parse_pagination_args()
    sort_order = request.args.get('sort_order', 'asc')
    if sort_order not in ('asc', 'desc'):
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "排序方向无效，仅支持 asc 或 desc")

    app = get_app_by_id(int(app_id))
    is_admin_or_creator = (
        user.user_role == UserRole.ADMIN
        or user.id == app.user_id
    )
    if not is_admin_or_creator:
        raise BusinessException(ErrorCode.PERMISSION_DENIED, "您没有权限查询该应用的对话历史")

    last_create_time = request.args.get('last_create_time')
    if last_create_time:
        last_create_time = datetime.strptime(last_create_time, '%Y&%m&%d&%H&%M&%S')

    chat_records = list_chat_history(
        page, per_page, app.id,
        message_type="ALL", sort_order=sort_order,
        last_create_time=last_create_time,
    )
    return success_response(chat_records)