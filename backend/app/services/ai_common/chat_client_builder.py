import os
from typing import Any, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from backend.app.services.ai_common.advisor import AdvisorChain
from backend.app.services.ai_common.llm_client import ChatClient
from backend.app.services.ai_common.tools import filter_tools_by_names, get_all_tools_in_module


load_dotenv()


class ChatClientBuilder:
    """LLM客户端构建器"""

    def __init__(self):
        self._api_key = os.getenv('TONGYI_API_KEY')
        self._base_url = os.getenv('TONGYI_OPENAI_COMPATIBLE_BASE_URL')
        self._model = os.getenv('TONGYI_MODEL')
        self._temperature = 0.7
        self._max_tokens = None
        self._top_p = 1.0
        self._frequency_penalty = 0.0
        self._presence_penalty = 0.0
        self._system_prompt = "You are a helpful assistant."
        self._timeout = 60
        self._max_retries = 3
        self._advisor_chain = AdvisorChain()
        self._response_format = None
        self._available_tools = []

    def set_api_key(self, api_key: str) -> 'ChatClientBuilder':
        """设置API密钥"""
        self._api_key = api_key
        return self

    def set_base_url(self, base_url: str) -> 'ChatClientBuilder':
        """设置基础URL"""
        self._base_url = base_url
        return self

    def set_model(self, model: str) -> 'ChatClientBuilder':
        """设置模型名称"""
        self._model = model
        return self

    def set_temperature(self, temperature: float) -> 'ChatClientBuilder':
        """
        设置温度参数
        范围: 0.0-2.0，值越高输出越随机，越低越确定
        """
        if not 0.0 <= temperature <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        self._temperature = temperature
        return self

    def set_max_tokens(self, max_tokens: int) -> 'ChatClientBuilder':
        """设置最大生成token数"""
        if max_tokens and max_tokens <= 0:
            raise ValueError("Max tokens must be positive")
        self._max_tokens = max_tokens
        return self

    def set_top_p(self, top_p: float) -> 'ChatClientBuilder':
        """
        设置核采样参数
        范围: 0.0-1.0，值越小生成越保守
        """
        if not 0.0 <= top_p <= 1.0:
            raise ValueError("Top p must be between 0.0 and 1.0")
        self._top_p = top_p
        return self

    def set_frequency_penalty(self, penalty: float) -> 'ChatClientBuilder':
        """
        设置频率惩罚
        范围: -2.0-2.0，正值降低重复token的概率
        """
        if not -2.0 <= penalty <= 2.0:
            raise ValueError("Frequency penalty must be between -2.0 and 2.0")
        self._frequency_penalty = penalty
        return self

    def set_presence_penalty(self, penalty: float) -> 'ChatClientBuilder':
        """
        设置存在惩罚
        范围: -2.0-2.0，正值鼓励谈论新话题
        """
        if not -2.0 <= penalty <= 2.0:
            raise ValueError("Presence penalty must be between -2.0 and 2.0")
        self._presence_penalty = penalty
        return self

    def set_system_prompt(self, prompt: str) -> 'ChatClientBuilder':
        """设置系统提示词"""
        self._system_prompt = prompt
        return self

    def set_timeout(self, timeout: int) -> 'ChatClientBuilder':
        """设置超时时间（秒）"""
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self._timeout = timeout
        return self

    def set_response_format(self, response_format: Any) -> 'ChatClientBuilder':
        """设置响应格式"""
        self._response_format = response_format
        return self

    def set_max_retries(self, retries: int) -> 'ChatClientBuilder':
        """设置最大重试次数"""
        if retries < 0:
            raise ValueError("Max retries cannot be negative")
        self._max_retries = retries
        return self

    def set_advisor_chain(self, advisor_chain: AdvisorChain) -> 'ChatClientBuilder':
        """设置拦截器链"""
        self._advisor_chain = advisor_chain
        return self

    def add_pre_advisor(self, advisor) -> 'ChatClientBuilder':
        """添加前置拦截器"""
        self._advisor_chain.add_pre_advisor(advisor)
        return self

    def add_post_advisor(self, advisor) -> 'ChatClientBuilder':
        """添加后置拦截器"""
        self._advisor_chain.add_post_advisor(advisor)
        return self

    def add_stream_post_advisor(self, advisor) -> 'ChatClientBuilder':
        """添加流式后置拦截器"""
        self._advisor_chain.add_stream_post_advisor(advisor)
        return self

    def add_tools(self, tools: list) -> 'ChatClientBuilder':
        """直接添加 BaseTool 实例列表（可以是无状态工具或已注入 context 的工具）"""
        self._available_tools.extend(tools)
        return self

    def add_tools_by_names(self, tool_names: List[str]) -> 'ChatClientBuilder':
        """
        按名称注册无状态工具（不带 context 的版本）。
        找不到指定名字的工具时会发出警告但不报错。
        """
        all_tools = get_all_tools_in_module()
        selected = filter_tools_by_names(all_tools, tool_names)
        self._available_tools.extend(selected)
        return self

    def add_tools_with_context_by_names(self, tool_names: List[str] | None = None) -> 'ChatClientBuilder':
        """
        按名称注册带 context 的工具

        Args:
            tool_names: 可选，指定只注册哪些工具；为 None 时注册所有带 _with_context 的工具

        业务侧用法：
            builder.add_tools_with_context(
                tool_names=["文件写入工具"]  # 可选，不传就注册全部
            )
        """
        from backend.app.services.ai_common.tools import tools_factory_with_context
        self._available_tools.extend(tools_factory_with_context(tool_names))
        return self

    def build(self) -> 'ChatClient':
        """构建ChatClient实例"""
        from backend.app.services.ai_common.llm_client import ChatClient

        llm_params = {
            'api_key': self._api_key,
            'base_url': self._base_url,
            'model': self._model,
            'temperature': self._temperature,
            'top_p': self._top_p,
            'frequency_penalty': self._frequency_penalty,
            'presence_penalty': self._presence_penalty,
            'timeout': self._timeout,
            'max_retries': self._max_retries,
        }

        if self._max_tokens:
            llm_params['max_tokens'] = self._max_tokens
            if 'qwen' in self._model.lower():   # Qwen模型需要特殊处理，md这里不看官方文档还真不知道参数名不一样。。。
                llm_params['max_completion_tokens'] = self._max_tokens

        if self._response_format:
            llm_params['response_format'] = self._response_format

        chat_llm = ChatOpenAI(**llm_params)

        if self._available_tools:
            chat_llm = chat_llm.bind_tools(self._available_tools)

        return ChatClient(
            chat_llm=chat_llm,
            system_prompt=self._system_prompt,
            advisor_chain=self._advisor_chain,
            available_tools=self._available_tools,
        )


def create_default_chat_client() -> ChatClient:
    """创建默认配置的聊天客户端"""
    return ChatClientBuilder().build()
