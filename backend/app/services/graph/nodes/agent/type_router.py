"""
智能路由节点（代码生成模式选择）
对应流程图中「智能路由Agent」+「选择生成模式」判断框

职责：根据 enhanced_prompt 判断最合适的代码生成类型
- HTML       : 需求简单、内容固定的纯展示型网站
- MULTI_FILE : 有简单交互但逻辑少的前端三件套
- VUE_PROJECT: 复杂需求（状态共享、组件复用、数据交互、多人协同等）
"""
import logging

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.ai_common.prompts import CODE_GENERATE_ROUTING_SYSTEM_PROMPT
from backend.app.services.graph.nodes.agent import create_spec_llm_in_graph
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


def type_router_node(state: WorkflowState) -> dict:
    """
    根据增强后的提示词，路由到最合适的代码生成类型

    Args:
        state: 当前工作流状态

    Returns:
        dict: 要更新到 state 中的字段（code_gen_type）
    """
    enhanced_prompt = state.get("enhanced_prompt", "")

    llm_client = create_spec_llm_in_graph(
        system_prompt=CODE_GENERATE_ROUTING_SYSTEM_PROMPT,
        response_format=CodeFileType.get_response_format(),
    )

    messages = [{"role": "user", "content": enhanced_prompt}]
    code_gen_type = ""
    try:
        result = llm_client.chat_structured(messages, CodeFileType)
        code_gen_type = result.value if result else CodeFileType.HTML.value
        logger.info(f"[type_router] 路由结果: {code_gen_type}")
    except Exception as e:
        logger.error(f"[type_router] 路由失败，降级为 HTML: {e}")
        code_gen_type = CodeFileType.HTML.value
    finally:
        # 如果是 new_build 任务，需要保存系统提示词到对话历史和内存
        task_type = state.get("task_type", "")
        app_id = state.get("app_id", "")
        if task_type == "new_build":
            chat_memory_manager = get_chat_memory_manager(memory_only=True)     # 开发阶段 memory_only 为 True，后续上线再 False
            chat_memory_manager.add_message(
                app_id=app_id,
                role="system",
                content=CodeFileType.get_system_prompt(code_gen_type),
            )
        # TODO 开发阶段没有 flask 上下文，注释掉这段代码，不存数据库了，后续上线再开启
        # user_id = state.get("user_id", "")
        # create_chat_history(
        #     message=CodeFileType.get_system_prompt(code_gen_type),
        #     message_type=ChatMessageType.SYSTEM.value,
        #     app_id=app_id,
        #     user_id=user_id,
        # )
    return {
        "messages": {"role": "system", "content": CodeFileType.get_system_prompt(code_gen_type)},
        "code_gen_type": code_gen_type,
        "current_node": "type_router",
    }
