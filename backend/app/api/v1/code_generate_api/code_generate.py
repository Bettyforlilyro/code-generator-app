from flask import request, g

from backend.app.api.v1.code_generate_api import code_generate_bp
from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.exceptions.error_codes import ErrorCode
from backend.app.common.utils.auth import login_required
from backend.app.models.app_model import AppModel
from backend.app.schemas.responses.BaseResponse import error_response, stream_response
from backend.app.services.ai_generator_facade import AICodeGeneratorFacade


@code_generate_bp.route('/generate', methods=['POST'])
@login_required
def generate_code_stream():
    """
    生成代码并保存到服务器本地的文件，请求体参数：
    - "prompt": 代码生成的提示词，必填
    - "code_gen_type": 生成的代码文件类型（例如html），必填
    - "app_id": 应用ID，必填
    Returns:
        stream_response: 流式响应，包含生成的代码和文件路径
        data包含以下字段:
            - "type": "token" 或 "done"
            - "content": 生成的代码或文件路径（仅当 type 为 "done" 时）
            - "file_path": 生成的文件路径（仅当 type 为 "done" 时）
            - "error": 错误信息（仅当 type 为 "error" 时）
        返回响应示例：
        - {
            "event": "message",
            "data": {
                "code": 20000, "message": "操作成功",
                "data": {"type": "token", "content": "codex"}
            }
        }
        - {
            "event": "message",
            "data": {
                "code": 20000, "message": "操作成功",
                "data": {
                    "type": "complete",
                    "file_path": "D:\\projects\\code-generator-app\\backend\\app\\html\\20260823201838.html",
                    "description": "这是一个HTML文件"
                }
            }
        }
        - {
            "event": "done",
            "data": {
                "code": 20000, "message": "流结束",
                "data": {}
            }
        }
    """
    user = g.current_user
    json_data = request.get_json()
    if not json_data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")
    app_id = json_data.get('app_id')
    if not app_id:
        return error_response(ErrorCode.MISSING_PARAMETER, "app_id不能为空")
    prompt = json_data.get('prompt')
    if not prompt:
        return error_response(ErrorCode.MISSING_PARAMETER, "prompt不能为空")
    code_gen_type = json_data.get('code_gen_type')
    if not code_gen_type:
        return error_response(ErrorCode.MISSING_PARAMETER, "code_gen_type不能为空")
    app = AppModel.query.filter_by(id=app_id).first_or_none()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在")
    if app.user_id != user.id:
        return error_response(ErrorCode.PERMISSION_DENIED, "您没有权限操作该应用")
    code_gen_type = json_data.get('code_gen_type')
    generator = AICodeGeneratorFacade.generate_code_and_save_file_streaming(prompt, CodeFileType(code_gen_type), app_id)
    return stream_response(generator)