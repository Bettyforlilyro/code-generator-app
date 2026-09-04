from flask import g

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import login_required
from backend.app.common.utils.request_helpers import parse_json_body
from backend.app.schemas.responses.BaseResponse import stream_response
from backend.app.services.code_generate_service import (
    validate_and_prepare_code_generation,
    build_code_generator,
    persist_chat_after_generation,
)


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
            - init_prompt
            - code_gen_type
            - app_id
          properties:
            init_prompt:
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
    json_data = parse_json_body()

    app_id = json_data.get('app_id')
    if not app_id or int(app_id) <= 0:
        raise BusinessException(ErrorCode.BAD_REQUEST, "app_id必须填写且应该为大于0的整数")

    init_prompt = json_data.get('init_prompt')
    if not init_prompt:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "init_prompt不能为空")

    code_gen_type = json_data.get('code_gen_type')
    if not code_gen_type:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "code_gen_type不能为空")

    if not CodeFileType.is_valid_file_type(code_gen_type):
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "code_gen_type无效")

    # 1. 应用校验 + 权限校验 + code_gen_type 持久化 + 系统 Prompt 注入
    validate_and_prepare_code_generation(int(app_id), user.id, code_gen_type)

    # 2. 构建流式生成器
    generator = build_code_generator(init_prompt, CodeFileType(code_gen_type), int(app_id))

    user_id = user.id

    def on_done(chunks: list):
        persist_chat_after_generation(int(app_id), user_id, init_prompt, chunks)

    def on_error(error: Exception, chunks: list):
        persist_chat_after_generation(int(app_id), user_id, init_prompt, chunks)
        import logging
        full = ''.join(c['d'] for c in chunks if isinstance(c, dict) and 'd' in c)
        logging.error(f"AI回复异常，错误信息: {str(error)}, 已回复内容: {full}")

    return stream_response(generator, use_wrapper=False, on_done=on_done, on_error=on_error)