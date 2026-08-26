from flask import request, g

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.exceptions.error_codes import ErrorCode
from backend.app.common.utils.auth import login_required
from backend.app.models.app_model import AppModel
from backend.app.schemas.responses.BaseResponse import error_response, stream_response
from backend.app.services.ai_generator_facade import AICodeGeneratorFacade


@code_bp.route('/generate', methods=['POST'])
@login_required
def generate_code_stream():
    """
    流式生成代码并保存到服务器本地文件
    ---
    tags:
      - 代码生成
    summary: 流式生成代码
    description: 根据用户提供的Prompt和代码类型，通过AI流式生成代码并保存到服务器本地文件，使用SSE（Server-Sent Events）返回流式响应
    consumes:
      - application/json
    produces:
      - text/event-stream
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
            - prompt
            - code_gen_type
            - app_id
          properties:
            prompt:
              type: string
              description: 代码生成的提示词
              example: 创建一个现代化的个人博客网站
            code_gen_type:
              type: string
              description: 生成的代码文件类型
              example: html
              enum: ['html', 'multi_file']
            app_id:
              type: integer
              description: 应用ID
              example: 1
    responses:
      200:
        description: 流式响应，包含生成的代码token、完成信息、文件路径
      400:
        description: 请求参数错误
      401:
        description: 未登录或Token无效
      403:
        description: 权限不足
      500:
        description: 服务器内部错误
    """
    user = g.current_user
    json_data = request.get_json()
    if not json_data:
        return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")
    app_id = json_data.get('app_id')
    if not app_id or app_id <= 0:
        return error_response(ErrorCode.BAD_REQUEST, "app_id必须填写且应该为大于0的整数")
    init_prompt = json_data.get('init_prompt')
    if not init_prompt:
        return error_response(ErrorCode.MISSING_PARAMETER, "init_prompt不能为空")
    code_gen_type = json_data.get('code_gen_type')
    if not code_gen_type:
        return error_response(ErrorCode.MISSING_PARAMETER, "code_gen_type不能为空")
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在")
    if app.user_id != user.id:
        return error_response(ErrorCode.PERMISSION_DENIED, "您没有权限操作该应用")
    generator = AICodeGeneratorFacade.generate_code_and_save_file_streaming(init_prompt, CodeFileType(code_gen_type), app_id)
    return stream_response(generator, use_wrapper=False)
