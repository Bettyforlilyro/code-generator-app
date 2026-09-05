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
    """流式响应数据块"""

    def __init__(self, content: str, is_last: bool = False):
        self.content = content
        self.is_last = is_last


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
