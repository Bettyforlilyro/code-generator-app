import logging
from datetime import datetime
import sys, io

from backend.app.services.ai_common.advisor import PreAdvisor, AdvisorContext, PostAdvisor, StreamPostAdvisor, \
    StreamChunk

# 强制设置标准输出为UTF-8编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置日志处理器，设置UTF-8编码
logger = logging.getLogger('ChatAdvisor')
logger.setLevel(logging.INFO)

# 创建控制台处理器并设置UTF-8编码
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# 设置格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(console_handler)


class LogPreAdvisor(PreAdvisor):
    """前置日志拦截器 - 记录用户提问"""

    @property
    def name(self) -> str:
        return "LogPreAdvisor"

    def pre_handle(self, context: AdvisorContext) -> AdvisorContext:
        # 获取最后一条用户消息
        user_messages = [msg for msg in context.messages if msg['role'] == 'user']
        if user_messages:
            last_user_message = user_messages[-1]['content']
            logger.info(
                f"[用户提问] 会话ID: {context.conversation_id} | "
                f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"内容: {last_user_message}"
            )

        # 可以在metadata中记录额外信息
        context.metadata['user_question_time'] = datetime.now().isoformat()

        return context


class LogPostAdvisor(PostAdvisor):
    """后置日志拦截器 - 记录AI回答"""

    @property
    def name(self) -> str:
        return "LogPostAdvisor"

    def post_handle(self, context: AdvisorContext) -> AdvisorContext:
        if context.response:
            logger.info(
                f"[AI回答] 会话ID: {context.conversation_id} | "
                f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"内容: {context.response}"
            )

        # 记录响应时间
        context.metadata['ai_response_time'] = datetime.now().isoformat()

        return context


class LogStreamPostAdvisor(StreamPostAdvisor):
    """流式后置日志拦截器 - 逐块记录AI回答"""

    def __init__(self):
        self._full_response = ""
        self._chunk_count = 0

    @property
    def name(self) -> str:
        return "LogStreamPostAdvisor"

    def post_handle_stream(self, chunk: StreamChunk, context: AdvisorContext) -> StreamChunk:
        self._chunk_count += 1
        self._full_response += chunk.content

        # 记录每个数据块
        logger.info(
            f"[AI回答-流式块#{self._chunk_count}] 会话ID: {context.conversation_id} | "
            f"内容片段: {chunk.content}"
        )

        # 如果是最后一个块，记录完整响应
        if chunk.is_last:
            logger.info(
                f"[AI回答-流式完成] 会话ID: {context.conversation_id} | "
                f"总块数: {self._chunk_count} | "
                f"完整内容: {self._full_response}"
            )
            # 重置状态，为下次对话做准备
            context.metadata['ai_response_time'] = datetime.now().isoformat()
            context.metadata['stream_chunk_count'] = self._chunk_count
            self._full_response = ""
            self._chunk_count = 0

        return chunk
