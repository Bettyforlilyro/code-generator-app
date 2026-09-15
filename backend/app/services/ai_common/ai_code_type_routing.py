from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.services.ai_common.chat_client_builder import ChatClientBuilder
from backend.app.services.ai_common.prompts import CODE_GENERATE_ROUTING_SYSTEM_PROMPT


class AiCodeTypeRouting:

    @staticmethod
    def route_code_gen_type(init_prompt: str) -> CodeFileType:
        """
        由AI根据用户初始提示词，智能路由代码生成类型到对应的模型
        Args:
            init_prompt: 初始提示词
        Returns:
            对应的代码生成类型
        """
        llm_client = (ChatClientBuilder()
                      .set_response_format(CodeFileType.get_response_format())
                      .set_system_prompt(CODE_GENERATE_ROUTING_SYSTEM_PROMPT)
                      .build())
        messages = [{"role": "user", "content": init_prompt}]
        response = llm_client.chat_structured(messages, CodeFileType)
        return response.value if response else CodeFileType.HTML
