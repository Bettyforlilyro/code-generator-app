import logging

from flask import g

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.emuns import CodeFileType
from backend.app.common.exceptions import ErrorCode, BusinessException
from backend.app.common.utils import login_required
from backend.app.common.utils import parse_json_body
from backend.app.middleware import my_limiter
from backend.app.schemas.responses import stream_response
from backend.app.services.ai_common import get_system_prompt
from backend.app.services.app_service import update_app_code_gen_type_svc, update_app_system_prompt_svc
from backend.app.services.code_generate_service import (
    validate_and_prepare_code_generation_svc,
    build_code_generator_svc,
    persist_chat_after_generation_svc,
)

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

    # ── 新增：是否使用 LangGraph 工作流 ──────────────
    use_graph = json_data.get('use_graph', False)

    code_gen_type = json_data.get('code_gen_type')
    if not code_gen_type and not use_graph:
        raise BusinessException(ErrorCode.MISSING_PARAMETER, "code_gen_type不能为空")

    if code_gen_type and not CodeFileType.is_valid_file_type(code_gen_type):
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "code_gen_type无效")

    user_id = user.id

    if use_graph:
        app_id = json_data.get('app_id')    # 首次创建时可能为空（在graph中插入数据库时才拿到，是正常的），因此这里就不加校验了
        generator = _build_workflow_generator(prompt, user_id, app_id=app_id)

        # 工作流模式：chat_history_save 节点已自动持久化对话历史，路由节点已自动更新 code_gen_type 持久化 + 系统 Prompt 存数据库
        # 但 on_done / on_error 仍然需要，用于统一回调签名
        def on_done(chunks):
            pass  # 已由工作流内部 chat_history_save 节点处理

        def on_error(error, chunks):
            _logger.error(f"[workflow] 工作流执行异常: {str(error)}, app_id={app_id}")
            return "AI 暂时不能回答这个问题"
    else:
        app_id = json_data.get('app_id')
        if not app_id or int(app_id) <= 0:
            raise BusinessException(ErrorCode.BAD_REQUEST, "app_id必须填写且应该为大于0的整数")
        # ── 公共：应用校验 + 权限校验 ──
        validate_and_prepare_code_generation_svc(int(app_id), user.id, code_gen_type)
        # ── 原有逻辑保持不变 code_gen_type 持久化 + 系统 Prompt 存数据库 ────────────────────────────
        update_app_code_gen_type_svc(int(app_id), code_gen_type)
        update_app_system_prompt_svc(int(app_id), user_id, get_system_prompt(code_gen_type))
        generator = build_code_generator_svc(prompt, CodeFileType(code_gen_type), int(app_id))

        def on_done(chunks: list[tuple[str, dict]]):
            persist_chat_after_generation_svc(int(app_id), user_id, prompt, chunks)

        def on_error(error: Exception, chunks: list[tuple[str, dict]]):
            persist_chat_after_generation_svc(int(app_id), user_id, prompt, chunks)
            full = ''.join(c['d'] for c in chunks if isinstance(c, dict) and 'd' in c)
            _logger.error(f"AI回复异常，错误信息: {str(error)}, 已回复内容: {full}")
            return "AI 暂时不能回答这个问题"

    return stream_response(generator, use_wrapper=False, on_done=on_done, on_error=on_error)


def _build_workflow_generator(original_prompt: str, user_id: int, app_id: int | None = None):
    """
    构建 LangGraph 工作流流式生成器

    适配工作流 run_workflow_streaming 的三元组输出 → stream_response 期望的二元组

    工作流产出:
        ("stream", event_type, data)  ← 前端关心的流式事件
        ("state", node_name, updates)  ← 内部调试用，过滤掉

    stream_response 期望:
        (event, data)                   ← SSE 的 event 和 data
    """
    from backend.app.services.graph.workflow_graph import run_workflow_streaming

    for kind, *payload in run_workflow_streaming(
            original_prompt=original_prompt,
            app_id=app_id,
            user_id=user_id,
    ):
        if kind == "stream":
            # ("stream", event_type, data) → (event_type, data)
            event_type, data = payload
            yield event_type, data
        # kind == "state": 过滤掉，前端不需要内部节点状态更新
