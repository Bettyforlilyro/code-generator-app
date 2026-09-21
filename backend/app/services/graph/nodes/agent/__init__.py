"""
Agent节点 通用方法
"""
from typing import Any, Optional

from backend.app.services.ai_common.chat_client_builder import ChatClientBuilder
from backend.app.services.ai_common.llm_client import ChatClient
from backend.app.services.ai_common.llm_client_pool import get_or_create


def create_spec_llm_in_graph(
        system_prompt: str,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        response_format: Any = None
) -> ChatClient:
    """
    返回一个指定模型的 ChatClient 实例，默认使用 qwen 系列模型
    详细默认值请参考 backend.app.services.ai_common.chat_client_builder.ChatClientBuilder

    Args:
        system_prompt: 系统提示，用于引导模型的行为
        model_name: 要使用的模型名称
        base_url: OpenAI API 基础 URL
        api_key: OpenAI API 密钥
        response_format: 响应格式，用于指定模型输出的格式

    Returns:
        ChatClient 实例，ChatClient已经提供了获取结构化响应的各种chat方法
    """
    builder = (ChatClientBuilder()
               .set_model(model_name)
               .set_base_url(base_url)
               .set_response_format(response_format)
               .set_api_key(api_key)
               .set_system_prompt(system_prompt)
               )
    return get_or_create(builder)
