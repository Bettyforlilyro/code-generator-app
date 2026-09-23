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
        temperature: Optional[float] = None,
        response_format: Any = None,
        tools: Optional[list] = None,
        timeout: Optional[int] = None,
) -> ChatClient:
    """
    返回一个指定模型的 ChatClient 实例，默认使用 qwen 系列模型
    详细默认值请参考 backend.app.services.ai_common.chat_client_builder.ChatClientBuilder

    Args:
        system_prompt: 系统提示，用于引导模型的行为
        model_name: 要使用的模型名称
        base_url: OpenAI API 基础 URL
        api_key: OpenAI API 密钥
        temperature: 温度参数，用于控制模型的随机性
        response_format: 响应格式，用于指定模型输出的格式
        tools: 要绑定的工具列表，类型是 list[Tool]，每个 Tool 是一个 langchain_core.tools.Tool 实例
        timeout: 超时时间，单位秒

    Returns:
        ChatClient 实例，ChatClient已经提供了获取结构化响应的各种chat方法
    """
    builder = ChatClientBuilder()
    if model_name:
        builder = builder.set_model(model_name)
    if base_url:
        builder = builder.set_base_url(base_url)
    if api_key:
        builder = builder.set_api_key(api_key)
    if temperature:
        builder = builder.set_temperature(temperature)
    if response_format:
        builder = builder.set_response_format(response_format)
    if system_prompt:
        builder = builder.set_system_prompt(system_prompt)
    if tools:
        builder.add_tools(tools)
    if timeout:
        builder = builder.set_timeout(timeout)
    return get_or_create(builder)
