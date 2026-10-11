import logging

from flask import g

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.exceptions import ErrorCode, BusinessException
from backend.app.common.utils import login_required
from backend.app.common.utils import parse_json_body
from backend.app.middleware import my_limiter
from backend.app.schemas.responses import stream_response
from backend.app.services.code_streaming_generator_service import get_streaming_generator

_logger = logging.getLogger(__name__)


@code_bp.route('/generate', methods=['POST'])
@login_required
@my_limiter({
    "user": "10 per minute",
    "ip": "20 per minute",
})
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

    prompt = json_data.get('init_prompt')
    if not prompt:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "init_prompt不能为空")

    use_graph = json_data.get('use_graph', False)
    code_gen_type = json_data.get('code_gen_type')
    app_id = json_data.get('app_id')
    user_id = user.id   # 必须显示保存user_id，SSE会话on_done调用时user对象不会保存
    generator = get_streaming_generator(use_graph, app_id=int(app_id), code_gen_type=code_gen_type)

    return stream_response(
        generator.generate(prompt, user_id),
        use_wrapper=False,
        on_done=lambda chunks: generator.on_done(chunks, app_id, user_id, prompt),
        on_error=lambda err, chunks: generator.on_error(err, chunks, app_id, user_id, prompt)
    )
