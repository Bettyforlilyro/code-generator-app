"""
Advisor拦截器模块
提供链式拦截器机制，支持前置和后置处理
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


logger = logging.getLogger(__name__)


class AdvisorContext:
    """Advisor执行上下文，传递请求和响应数据"""

    def __init__(self, messages: List[Dict[str, str]], conversation_id: Optional[str] = None):
        self.messages = messages
        self.conversation_id = conversation_id
        self.response: Optional[str] = None
        self.metadata: Dict[str, Any] = {}


class StreamChunk:
    """
    流式响应数据块

    chunk_type 字段说明前端应该怎么渲染：
        "text"        —— 普通对话文本，用 Markdown/纯文本渲染（默认值）
        "tool_start"  —— 工具开始调用，前端可以渲染「工具调用卡片」的标题部分
        "tool_end"    —— 工具执行完毕，前端可以更新「工具调用卡片」为完成状态
        "error"       —— 错误信息，前端可以用红色/警告样式渲染
        "done"        —— 整轮结束（is_last=True 的时候 chunk_type=done）

    metadata 字段存放结构化数据，前端可以直接用：
        tool_start 时: {tool_name, args_str, tool_call_id}
        tool_end 时:   {tool_name, result_str, tool_call_id, success: bool}
    """

    TYPE_TEXT = "text"
    TYPE_TOOL_START = "tool_start"
    TYPE_TOOL_END = "tool_end"
    TYPE_ERROR = "error"
    TYPE_WEB_SEARCH = "web_search"
    TYPE_WEB_SEARCH_DONE = "web_search_done"
    TYPE_DONE = "done"

    def __init__(
        self,
        content: str,
        is_last: bool = False,
        chunk_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.content = content
        self.is_last = is_last
        self.chunk_type = chunk_type
        self.metadata = metadata or {}


class PreAdvisor(ABC):
    """前置拦截器接口，在用户提问后、AI调用前执行"""

    @abstractmethod
    def pre_handle(self, context: AdvisorContext) -> AdvisorContext:
        """
        前置处理逻辑

        Args:
            context: 包含用户消息和会话信息的上下文

        Returns:
            处理后的上下文（可以修改messages等）
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """拦截器名称"""
        pass


class PostAdvisor(ABC):
    """后置拦截器接口，在AI输出回答后执行"""

    @abstractmethod
    def post_handle(self, context: AdvisorContext) -> AdvisorContext:
        """
        后置处理逻辑

        Args:
            context: 包含AI响应的上下文

        Returns:
            处理后的上下文（可以修改response等）
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """拦截器名称"""
        pass


class StreamPostAdvisor(ABC):
    """流式后置拦截器接口，在AI流式输出时逐块处理"""

    @abstractmethod
    def post_handle_stream(self, chunk: StreamChunk, context: AdvisorContext) -> StreamChunk:
        """
        流式后置处理逻辑，对每个数据块进行处理

        Args:
            chunk: 当前的流式数据块
            context: 包含AI响应的上下文

        Returns:
            处理后的数据块
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """拦截器名称"""
        pass


class AdvisorChain:
    """拦截器链管理器"""

    def __init__(self):
        self._pre_advisors: List[PreAdvisor] = []
        self._post_advisors: List[PostAdvisor] = []
        self._stream_post_advisors: List[StreamPostAdvisor] = []

    def add_pre_advisor(self, advisor: PreAdvisor) -> 'AdvisorChain':
        """添加前置拦截器"""
        self._pre_advisors.append(advisor)
        return self

    def add_post_advisor(self, advisor: PostAdvisor) -> 'AdvisorChain':
        """添加后置拦截器"""
        self._post_advisors.append(advisor)
        return self

    def add_stream_post_advisor(self, advisor: StreamPostAdvisor) -> 'AdvisorChain':
        """添加流式后置拦截器"""
        self._stream_post_advisors.append(advisor)
        return self

    def execute_pre_chain(self, context: AdvisorContext) -> AdvisorContext:
        """执行所有前置拦截器"""
        for advisor in self._pre_advisors:
            try:
                context = advisor.pre_handle(context)
            except Exception as e:
                logger.error("前置拦截器 %s 执行失败: %s", advisor.name, e)
                raise
        return context

    def execute_post_chain(self, context: AdvisorContext) -> AdvisorContext:
        """执行所有后置拦截器"""
        for advisor in self._post_advisors:
            try:
                context = advisor.post_handle(context)
            except Exception as e:
                logger.error("后置拦截器 %s 执行失败: %s", advisor.name, e)
                raise
        return context

    def execute_stream_post_chain(self, chunk: StreamChunk, context: AdvisorContext) -> StreamChunk:
        """执行所有流式后置拦截器"""
        processed_chunk = chunk
        for advisor in self._stream_post_advisors:
            try:
                processed_chunk = advisor.post_handle_stream(processed_chunk, context)
            except Exception as e:
                logger.error("流式后置拦截器 %s 执行失败: %s", advisor.name, e)
                raise
        return processed_chunk

    def clear(self):
        """清空所有拦截器"""
        self._pre_advisors.clear()
        self._post_advisors.clear()
        self._stream_post_advisors.clear()

    @property
    def pre_advisors(self) -> List[PreAdvisor]:
        return self._pre_advisors

    @property
    def post_advisors(self) -> List[PostAdvisor]:
        return self._post_advisors

    @property
    def stream_post_advisors(self) -> List[StreamPostAdvisor]:
        return self._stream_post_advisors
