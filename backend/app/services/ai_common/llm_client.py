import json
import re
import warnings
from typing import List

from langchain_core.messages import ToolMessage, AIMessage
from langchain_openai import ChatOpenAI

from backend.app.services.ai_common.advisor import AdvisorChain, AdvisorContext, StreamChunk
from backend.app.services.ai_common.tool_executor import (
    ToolExecResult,
    execute_single_tool,
    execute_tool_calls_batch,
    build_tool_start_content,
    build_tool_end_content,
)
from backend.app.services.ai_common.tools.tool_context_store import set_runtime_context

# 工具调用循环的最大迭代次数（防止 LLM 陷入无限调用）
MAX_TOOL_ITERATIONS = 10


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
        流式回复（**含完整工具调用循环**）

        工作原理：
            1. 流式收集本轮 LLM 响应，累积成完整 AIMessageChunk
            2. 收集过程中若有文本内容，实时 yield 给前端
            3. 收集完后检查 tool_calls：
                - 有 → 执行工具，把 AIMessage + ToolMessage 加入历史，继续下一轮
                - 无 → 这是最终回复，yield is_last=True 结束

        用户体验说明：
            - 如果 LLM 在决定调工具之前先输出了一些文本，这部分会实时流式展示
            - 工具执行 + 下一轮 LLM 响应期间显示调用的工具信息（当前仅yield开始调用工具和结束调用工具时的信息）

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

        accumulated: list = list(context.messages)
        full_response_text = ""
        iteration = 0

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # ===== 阶段 1：流式收集本轮 LLM 响应 =====
            # full_chunk 用于累积所有 AIMessageChunk（LangChain 支持 + 操作符自动处理碎片化 tool_calls）
            full_chunk = None
            planning_indices = set()  # 每轮重置；已 yield 过 loading 的 index

            for chunk in self._chat_llm.stream(accumulated):
                # 累积：AIMessageChunk（每次 + 都会把 tool_call_chunks 按 index 合并）
                full_chunk = chunk if full_chunk is None else full_chunk + chunk

                # 有纯文本内容 → 实时 yield（用户能立刻看到 AI 正在输出什么）
                if hasattr(chunk, 'content') and chunk.content:
                    stream_chunk = StreamChunk(content=chunk.content, is_last=False)
                    processed_chunk = self._advisor_chain.execute_stream_post_chain(
                        stream_chunk, context
                    )
                    full_response_text += processed_chunk.content
                    yield processed_chunk

                # 第一次检测到新工具（index+name）→ 给用户即时 loading 提示
                # 只展示概览（工具名），完整参数和执行结果交给 _build_tool_end_content
                tool_call_chunks = getattr(chunk, 'tool_call_chunks', None) or []
                for tc in tool_call_chunks:
                    index = tc.get('index')
                    tool_name = tc.get('name', '')
                    if index is None or index in planning_indices or not tool_name:
                        continue
                    planning_indices.add(index)
                    yield StreamChunk(
                        content=build_tool_start_content(tool_name),
                        chunk_type='tool_start',
                        is_last=False,
                        metadata={
                            "tool_name": tool_name,
                            "tool_call_id": tc.get('id', ''),
                            "tool_index": index,
                        }
                    )

            # ===== 阶段 2：从完整 chunk 检查是否有 tool_calls =====
            tool_calls = full_chunk.tool_calls
            if not tool_calls:  # 没有工具调用 —— 这就是最终回复，结束循环
                break

            # ===== 阶段 3：有工具调用，执行后继续下一轮 =====
            # 先把 AIMessage（包含 tool_calls）加入历史
            full_ai_message = AIMessage(
                content=full_chunk.content or "",
                tool_calls=tool_calls,
                id=full_chunk.id if full_chunk.id else None,
            )
            accumulated.append(full_ai_message)

            # 执行工具 —— 阶段 1 已经 yield 过 loading，这里只 yield tool_end（完整结果）
            tool_messages: List[ToolMessage] = []
            for item in self._execute_tool_calls_stream(tool_calls):
                tool_action = item[0]
                if tool_action == "tool_end":
                    _, tool_name, tool_call_id, success, content, tool_args = item
                    yield StreamChunk(
                        content=content,
                        is_last=False,
                        chunk_type="tool_end",
                        metadata={
                            "tool_name": tool_name,
                            "tool_call_id": tool_call_id,
                            "tool_result": 'success' if success else 'failed',
                        },
                    )
                elif tool_action == "tool_message":
                    tool_messages.append(item[1])

            accumulated.extend(tool_messages)

        # ===== 发送结束标记 =====
        final_chunk = StreamChunk(content="", is_last=True)
        processed_final = self._advisor_chain.execute_stream_post_chain(final_chunk, context)
        context.response = full_response_text

        # 执行完整的后置拦截器链（如果需要）
        # context = self._advisor_chain.execute_post_chain(context)

        yield processed_final

    # ---- 流式工具执行 ----
    def _execute_tool_calls_stream(self, tool_calls: list):
        """
        流式执行一批 tool_calls —— 生成器版本，边执行边 yield 状态标记。

        Yields:
            tuple: (kind, *payload)
            - ("tool_end",   tool_name, tool_call_id, success, content)
                - success: 工具执行是否成功（无异常）；content: 工具执行返回结果字符串
            - ("tool_message", ToolMessage)
        """
        for tc in tool_calls:
            r: ToolExecResult = execute_single_tool(tc, self._available_tools)

            # 查找失败：区分 "工具不存在" 和 "查找异常" 两种情况
            if not r.lookup_ok:
                if r.lookup_error.startswith("未注册"):
                    # 前端已经 yield 了 tool_start（chunk 阶段），这里必须 yield tool_end 配对
                    yield ("tool_end", r.tool_name, r.tool_call_id, False,
                           f"❌ **工具不存在**: `{r.tool_name}`（未在系统注册）\n\n")
                    yield ("tool_message", ToolMessage(
                        content=f"工具 【{r.tool_name}】 不存在", tool_call_id=r.tool_call_id))
                else:
                    yield ("tool_end", r.tool_name, r.tool_call_id, False,
                           f"❌ **工具查找异常**: `{r.tool_name}` — {r.lookup_error}\n\n")
                    yield ("tool_message", ToolMessage(
                        content=f"工具 【{r.tool_name}】 执行失败: {r.lookup_error}", tool_call_id=r.tool_call_id))
                continue

            # yield 工具结束标记
            content_end = build_tool_end_content(r.tool_name, r.tool_args, r.content, r.success)
            yield "tool_end", r.tool_name, r.tool_call_id, r.success, content_end, r.tool_args

            # yield 真正的 ToolMessage
            yield "tool_message", ToolMessage(content=r.content, tool_call_id=r.tool_call_id)

    def _execute_tool_calls(self, tool_calls: list) -> List[ToolMessage]:
        """
        执行一批 tool_calls，返回对应的 ToolMessage 列表。

        Args:
            tool_calls: LLM 返回的 tool_calls 列表，每个元素包含
                       {'name': str, 'args': dict, 'id': str}

        Returns:
            与 tool_calls 一一对应的 ToolMessage 列表（保持顺序）
        """
        return execute_tool_calls_batch(tool_calls, self._available_tools)

    @property
    def system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str):
        """设置系统提示词"""
        self._system_prompt = prompt