from flask import request

from backend.app.api.v1.code_generate_api import code_generate_bp
from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.exceptions.error_codes import ErrorCode
from backend.app.schemas.responses.BaseResponse import error_response, stream_response
from backend.app.services.ai_generator_facade import AICodeGeneratorFacade


@code_generate_bp.route('/generate', methods=['POST'])
def generate_code_stream():
    """
    生成代码并保存到服务器本地的文件
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
    json_data = request.get_json()
    if not json_data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")
    prompt = json_data.get('prompt')
    if not prompt:
        return error_response(ErrorCode.MISSING_PARAMETER, "prompt不能为空")
    code_file_type = json_data.get('code_file_type')
    if not code_file_type:
        return error_response(ErrorCode.MISSING_PARAMETER, "code_file_type不能为空")
    generator = AICodeGeneratorFacade.generate_code_and_save_file_streaming(prompt, CodeFileType(code_file_type))
    return stream_response(generator)
