from datetime import datetime

from flask import request, g

from backend.app.api.v1.app_management import app_management_bp
from backend.app.api.v1.chat_history_management.chat_history_service import list_chat_history
from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import login_required
from backend.app.models.app_model import AppModel
from backend.app.models.user import User
from backend.app.schemas.responses.BaseResponse import success_response


@app_management_bp.route('/<string:app_id>/chat_history', methods=['GET'])
@login_required
def get_chat_history(app_id: str):
    user = g.current_user
    # 解析并校验分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    sort_order = request.args.get('sort_order', 'asc', type=str)
    if page < 1:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "页码必须大于等于1")
    if per_page < 1 or per_page > 100:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "每页数量必须在1-100之间")
    if sort_order not in ('asc', 'desc'):
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "排序方向无效，仅支持 asc 或 desc")

    app = AppModel.query.filter_by(id=app_id).first()
    if not app:
        raise BusinessException(ErrorCode.APP_NOT_FOUND, f"应用不存在: id={app_id}")
    is_admin_or_creator = (User.query.filter_by(id=user.id, is_delete=0).first().user_role == UserRole.ADMIN
                           or user.id == app.user_id)
    if not is_admin_or_creator:
        raise BusinessException(ErrorCode.PERMISSION_DENIED, "您没有权限查询该应用的对话历史")
    last_create_time = request.args.get('last_create_time', None)
    # 将字符串的last_create_time转换为datetime对象
    if last_create_time:
        last_create_time = datetime.strptime(last_create_time, '%Y&%m&%d&%H&%M&%S')
    chat_records = list_chat_history(page, per_page, app.id,
                                     message_type="ALL", sort_order=sort_order,
                                     last_create_time=last_create_time)

    return success_response(chat_records)
