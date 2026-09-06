import json
import os
import re
import traceback
import warnings
from typing import Any, List

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage, AIMessage
from langchain_openai import ChatOpenAI

from backend.app.services.ai_common.advisor import AdvisorChain, AdvisorContext, StreamChunk
from backend.app.services.ai_common.tools import get_tools_with_context_by_names, get_all_tools_in_module
from backend.app.services.ai_common.tools.tool_context_store import set_runtime_context


# 工具调用循环的最大迭代次数（防止 LLM 陷入无限调用）
MAX_TOOL_ITERATIONS = 10

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
        selected = get_tools_with_context_by_names(all_tools, tool_names)
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


class ChatClient:
    """LLM聊天客户端

    提供三类能力：
    - chat / chat_without_system：同步非流式，含完整工具调用循环
    - chat_structured：同步非流式 + Pydantic 结构化解析
    - chat_stream：流式，**不含**工具调用循环（工具需在流式之外处理）
    """

    def __init__(
        self,
        chat_llm: ChatOpenAI,
        system_prompt: str = "You are a helpful assistant.",
        advisor_chain: AdvisorChain | None = None,
        available_tools: list | None = None,
    ):
        self._chat_llm = chat_llm
        self._system_prompt = system_prompt
        self._advisor_chain = advisor_chain or AdvisorChain()
        self._available_tools = available_tools or []

    # ==================== 私有辅助 ====================

    def _build_context(
        self,
        messages: list,
        conversation_id: str | None,
        with_system: bool = True,
    ) -> AdvisorContext:
        """组装 AdvisorContext：可选地拼接 system prompt + 执行 pre_chain

        Args:
            messages: 原始消息列表
            conversation_id: 会话 ID
            with_system: 是否在消息前拼接 system prompt（chat_stream 也要复用）

        Returns:
            经 pre_chain 处理后的 AdvisorContext
        """
        if with_system and self._system_prompt:
            full_messages = [{'role': 'system', 'content': self._system_prompt}] + messages
        else:
            full_messages = messages
        context = AdvisorContext(messages=full_messages, conversation_id=conversation_id)
        return self._advisor_chain.execute_pre_chain(context)

    def _invoke_with_tool_loop(
        self,
        context: AdvisorContext,
        tool_context: dict | None,
    ) -> AIMessage:
        """执行 LLM invoke + 完整工具调用循环

        Args:
            context: 已组装好的 AdvisorContext（pre_chain 已执行）
            tool_context: 传给工具的 runtime context（通过 contextvars）

        Returns:
            最终一轮 LLM 返回的 AIMessage（不再含 tool_calls）
        """
        if tool_context:
            set_runtime_context(tool_context)

        accumulated: list = list(context.messages)
        response = self._chat_llm.invoke(accumulated)

        # ---- 工具调用循环 ----
        iteration = 0
        while response.tool_calls and iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            accumulated.append(response)
            tool_messages = self._execute_tool_calls(response.tool_calls)
            accumulated.extend(tool_messages)

            response = self._chat_llm.invoke(accumulated)

        # 超出最大迭代次数的防护：强制截断 + 警告
        if iteration >= MAX_TOOL_ITERATIONS and response.tool_calls:
            warnings.warn(
                f"[ChatClient] 工具调用达到最大迭代次数 ({MAX_TOOL_ITERATIONS})，"
                f"强制截断。最后一条 tool_calls: {response.tool_calls}"
            )
            accumulated.append(response)
            response = AIMessage(
                content=response.content or "（工具调用达到上限，已截断）"
            )

        return response

    # ==================== 公开 API ====================

    def chat(
        self,
        messages: list,
        conversation_id: str | None = None,
        tool_context: dict | None = None,
    ) -> str:
        """同步非流式回复（含完整工具调用循环 + system prompt）

        Args:
            messages: 消息列表，格式为 [{'role': 'user/assistant/system', 'content': '...'}]
            conversation_id: 会话 ID，用于拦截器上下文
            tool_context: 工具调用上下文（通过 contextvars 传给每个工具）

        Returns:
            AI 回复的文本内容
        """
        context = self._build_context(messages, conversation_id, with_system=True)
        response = self._invoke_with_tool_loop(context, tool_context)
        context.response = response.content or ""
        context = self._advisor_chain.execute_post_chain(context)
        return context.response

    def chat_without_system(
        self,
        messages: list,
        conversation_id: str | None = None,
        tool_context: dict | None = None,
    ) -> str:
        """同步非流式回复（含完整工具调用循环，不含 system prompt）"""
        context = self._build_context(messages, conversation_id, with_system=False)
        response = self._invoke_with_tool_loop(context, tool_context)
        context.response = response.content or ""
        context = self._advisor_chain.execute_post_chain(context)
        return context.response

    def chat_structured(
        self,
        messages: list,
        pydantic_model,
        conversation_id: str | None = None,
        tool_context: dict | None = None,
    ):
        """
        发送消息并获取结构化的 Pydantic 模型结果

        Args:
            messages: 消息列表
            pydantic_model: 用于解析的 Pydantic 模型类（如 HtmlCodeResult, MultiFileCodeResult）
            conversation_id: 会话 ID
            tool_context: 工具调用上下文

        Returns:
            Pydantic 模型实例
        """
        response = self.chat(messages, conversation_id, tool_context)
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

    def chat_stream(
        self,
        messages: list,
        conversation_id: str | None = None,
        tool_context: dict | None = None,
    ):
        """
        发送消息并获取流式回复

        注意：流式模式**不执行工具调用循环**，工具需在流式之外处理。

        Args:
            messages: 消息列表，格式为 [{'role': 'user/assistant/system', 'content': '...'}]
            conversation_id: 会话 ID，用于拦截器上下文
            tool_context: 工具调用上下文

        Yields:
            StreamChunk: 流式响应数据块
        """
        context = self._build_context(messages, conversation_id, with_system=True)

        if tool_context:
            set_runtime_context(tool_context)

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

    def _execute_tool_calls(self, tool_calls: list) -> List[ToolMessage]:
        """
        执行一批 tool_calls，返回对应的 ToolMessage 列表。

        Args:
            tool_calls: LLM 返回的 tool_calls 列表，每个元素包含
                       {'name': str, 'args': dict, 'id': str}

        Returns:
            与 tool_calls 一一对应的 ToolMessage 列表（保持顺序）
        """
        tool_messages: List[ToolMessage] = []

        for tc in tool_calls:
            tool_name = tc['name']
            tool_args = tc.get('args', {})
            tool_call_id = tc.get('id', '')

            # 1. 在已注册工具中查找对应实例
            try:
                matched = get_tools_with_context_by_names(self._available_tools, [tool_name])
                if not matched:
                    raise ValueError(f"未注册的工具: {tool_name}")
                tool = matched[0]
            except Exception as e:
                tool_messages.append(ToolMessage(content=f"工具查找失败: {e}", tool_call_id=tool_call_id))
                continue

            # 2. 执行工具
            try:
                result = tool.invoke(tool_args)
                content = str(result) if not isinstance(result, str) else result
            except Exception as e:
                # 工具执行异常必须作为 ToolMessage 返回，LLM 才能感知
                content = f"工具执行异常: {type(e).__name__}: {e}\n{traceback.format_exc()}"

            # 3. 构造 ToolMessage（关键：必须传 tool_call_id 才能匹配回 tool_call）
            tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))

        return tool_messages

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