from backend.app.common.enums import CodeFileType
from backend.app.config import get_config
from .chat_client_builder import ChatClientBuilder
from .llm_client_pool import get_or_create_chat_client
from .prompts import CODE_GENERATE_ROUTING_SYSTEM_PROMPT


class AiCodeTypeRouting:

    @staticmethod
    def route_code_gen_type(init_prompt: str, app_id: str) -> CodeFileType:
        """
        由AI根据用户初始提示词，智能路由代码生成类型到对应的模型
        Args:
            init_prompt: 初始提示词
            app_id: 应用ID
        Returns:
            对应的代码生成类型
        """
        # 路由模型不需要太智能，节省成本，使用 qwen-flash 模型
        builder = (ChatClientBuilder()
                   .set_response_format(CodeFileType.get_response_format())
                   .set_base_url(get_config().MODEL_OPENAI_COMPATIBLE_BASE_URL)
                   .set_api_key(get_config().MODEL_API_KEY)
                   .set_model(get_config().ROUTER_MODEL_OPENAI_COMPATIBLE)
                   .set_system_prompt(CODE_GENERATE_ROUTING_SYSTEM_PROMPT))
        llm_client = get_or_create_chat_client(builder, str(app_id))
        messages = [{"role": "user", "content": init_prompt}]
        response = llm_client.chat_structured(messages, CodeFileType)   # CodeFileType 必须覆盖实现 model_validate_json
        return response.value if response else CodeFileType.HTML
