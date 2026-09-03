from typing import Any

from langchain_openai import ChatOpenAI

from backend.app.services.ai_common.advisor import AdvisorChain, AdvisorContext, StreamChunk
import os
from dotenv import load_dotenv


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

    def build(self) -> 'ChatClient':
        """构建ChatClient实例"""
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

        return ChatClient(
            chat_llm=chat_llm,
            system_prompt=self._system_prompt,
            advisor_chain=self._advisor_chain
        )


class ChatClient:
    """LLM聊天客户端"""

    def __init__(self, chat_llm: ChatOpenAI, system_prompt: str = "You are a helpful assistant.",
                 advisor_chain: AdvisorChain = None):
        self._chat_llm = chat_llm
        self._system_prompt = system_prompt
        self._advisor_chain = advisor_chain or AdvisorChain()

    def chat(self, messages: list, conversation_id: str = None) -> str:
        """
        发送消息并获取回复

        Args:
            messages: 消息列表，格式为 [{'role': 'user/assistant/system', 'content': '...'}]
            conversation_id: 会话ID，用于拦截器上下文

        Returns:
            AI回复的文本内容
        """
        if self._system_prompt:
            full_messages = [
                                {'role': 'system', 'content': self._system_prompt}
                            ] + messages
        else:
            full_messages = messages

        context = AdvisorContext(messages=full_messages, conversation_id=conversation_id)

        context = self._advisor_chain.execute_pre_chain(context)

        response = self._chat_llm.invoke(context.messages)
        context.response = response.content

        context = self._advisor_chain.execute_post_chain(context)

        return context.response

    def chat_without_system(self, messages: list, conversation_id: str = None) -> str:
        """
        发送消息并获取回复（不包含系统提示词）

        Args:
            messages: 消息列表

        Returns:
            AI回复的文本内容
        """
        context = AdvisorContext(messages=messages, conversation_id=conversation_id)

        context = self._advisor_chain.execute_pre_chain(context)

        response = self._chat_llm.invoke(context.messages)
        context.response = response.content

        context = self._advisor_chain.execute_post_chain(context)

        return context.response

    def chat_structured(self, messages: list, pydantic_model, conversation_id: str = None):
        """
        发送消息并获取结构化的Pydantic模型结果

        Args:
            messages: 消息列表
            pydantic_model: 用于解析的Pydantic模型类（如HtmlCodeResult, MultiFileCodeResult）
            conversation_id: 会话ID

        Returns:
            Pydantic模型实例
        """
        response = self.chat(messages, conversation_id)
        try:
            return pydantic_model.model_validate_json(response)
        except Exception as e:
            # 降级处理：尝试提取JSON再解析
            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return pydantic_model.model_validate(data)
            raise ValueError(f"无法将AI响应解析为{pydantic_model.__name__}: {e}\n原始响应: {response}")

    def chat_stream(self, messages: list, conversation_id: str = None):
        """
        发送消息并获取流式回复

        Args:
            messages: 消息列表，格式为 [{'role': 'user/assistant/system', 'content': '...'}]
            conversation_id: 会话ID，用于拦截器上下文

        Yields:
            StreamChunk: 流式响应数据块
        """
        if self._system_prompt:
            full_messages = [
                                {'role': 'system', 'content': self._system_prompt}
                            ] + messages
        else:
            full_messages = messages

        context = AdvisorContext(messages=full_messages, conversation_id=conversation_id)

        context = self._advisor_chain.execute_pre_chain(context)

        full_response = ""

        # 使用langchain的stream方法获取流式响应
        for chunk in self._chat_llm.stream(context.messages):
            if hasattr(chunk, 'content') and chunk.content:
                stream_chunk = StreamChunk(content=chunk.content, is_last=False)

                # 执行流式后置拦截器链
                processed_chunk = self._advisor_chain.execute_stream_post_chain(stream_chunk, context)

                full_response += processed_chunk.content

                yield processed_chunk

        # 发送最后一个标记块
        final_chunk = StreamChunk(content="", is_last=True)
        processed_final = self._advisor_chain.execute_stream_post_chain(final_chunk, context)

        # 保存完整响应到context
        context.response = full_response

        # 执行完整的后置拦截器链（如果需要）
        # context = self._advisor_chain.execute_post_chain(context)

        yield processed_final

    @property
    def system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str):
        """设置系统提示词"""
        self._system_prompt = prompt


def create_default_chat_client() -> ChatClient:
    """创建默认配置的聊天客户端"""
    return ChatClientBuilder().build()