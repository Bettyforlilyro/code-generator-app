import logging
from abc import ABC, abstractmethod
from typing import Optional

from backend.app.common.enums import ChatMessageType, CodeFileType
from backend.app.common.exceptions import ErrorCode, BusinessException
from backend.app.models import AppModel
from .ai_common import get_chat_memory_manager
from .ai_common.tools import get_all_tools_name
from .ai_generator_facade import AICodeGeneratorFacade
from .chat_history_service import create_chat_history_svc


logger = logging.getLogger(__name__)


class CodeGenerationStrategy(ABC):
    """代码生成策略抽象基类"""

    @abstractmethod
    def generate(self, prompt: str, user_id: int, **kwargs):
        """返回流式生成器（yield (event, data)）"""
        pass

    def on_done(self, chunks: list[tuple[str, dict]], app_id: int, user_id: int, prompt: str):
        """生成成功完成后的钩子（持久化等）"""
        pass

    def on_error(self, error: Exception, chunks: list[tuple[str, dict]], app_id: int, user_id: int, prompt: str) -> Optional[str]:
        """生成失败后的钩子，返回用户友好的错误消息（可选）"""
        return None


class FacadeGenerationStrategy(CodeGenerationStrategy):
    """原 AICodeGeneratorFacade 流式生成路径"""

    def __init__(self, app_id: int, code_gen_type: CodeFileType):
        self.app_id = app_id
        self.code_gen_type = code_gen_type

    # ===== generate 准备 + 构建 =====

    def generate(self, prompt: str, user_id: int, **kwargs):
        # 1. 权限校验
        self._validate_and_prepare(self.app_id, user_id, self.code_gen_type.value)
        # 2. 更新 code_gen_type + 写入系统 Prompt（原来在 API 层散落的逻辑内聚到这里）
        from .app_service import update_app_code_gen_type_svc, update_app_system_prompt_svc
        from .prompts import get_system_prompt
        update_app_code_gen_type_svc(self.app_id, self.code_gen_type.value)
        update_app_system_prompt_svc(self.app_id, user_id, get_system_prompt(self.code_gen_type))
        # 3. 构建生成器
        return self._build_generator(prompt, self.code_gen_type, self.app_id)

    # ===== 成功/失败钩子 =====

    def on_done(self, chunks: list[tuple[str, dict]], app_id: int, user_id: int, prompt: str):
        self._persist_chat(app_id, user_id, prompt, chunks)

    def on_error(self, error: Exception, chunks: list[tuple[str, dict]], app_id: int, user_id: int, prompt: str) -> Optional[str]:
        self._persist_chat(app_id, user_id, prompt, chunks)
        full = ''.join(data['d'] for (event, data) in chunks if isinstance(data, dict) and 'd' in data)
        logger.error(f"AI回复异常，错误信息: {str(error)}, 已回复内容: {full}")
        return "AI 暂时不能回答这个问题"

    @staticmethod
    def _validate_and_prepare(app_id: int, user_id: int, code_gen_type: str):
        app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
        if not app:
            raise BusinessException(ErrorCode.APP_NOT_FOUND, "应用不存在")
        if app.user_id != user_id:
            raise BusinessException(ErrorCode.PERMISSION_DENIED, "您没有权限操作该应用")

    @staticmethod
    def _build_generator(prompt: str, code_gen_type: CodeFileType, app_id: int):
        tools = None
        if code_gen_type == CodeFileType.VUE_PROJECT:
            tools = get_all_tools_name()
        return AICodeGeneratorFacade.generate_code_and_save_file_streaming(
            prompt, code_gen_type, app_id, tools=tools
        )

    @staticmethod
    def _persist_chat(app_id: int, user_id: int, init_prompt: str, chunks: list[tuple[str, dict]]):
        full_ai_response = ''
        for event, data in chunks:
            if event == 'message':
                full_ai_response += data['d']
            elif event == 'task_end':
                full_ai_response += data['info']
            elif event == 'error':
                full_ai_response += data['d']
        if not full_ai_response:
            return

        try:
            user_record = create_chat_history_svc(
                message=init_prompt,
                message_type=ChatMessageType.USER.value,
                app_id=app_id,
                user_id=user_id,
            )
            ai_record = create_chat_history_svc(
                message=full_ai_response,
                message_type=ChatMessageType.AI.value,
                app_id=app_id,
                user_id=user_id,
            )

            memory_manager = get_chat_memory_manager()
            memory_manager.add_message(
                app_id=int(app_id),
                role=ChatMessageType.USER.value,
                content=user_record.message,
                db_id=user_record.id,
                token_count=user_record.token_count,
            )
            memory_manager.add_message(
                app_id=int(app_id),
                role=ChatMessageType.AI.value,
                content=ai_record.message,
                db_id=ai_record.id,
                token_count=ai_record.token_count,
            )
        except Exception as e:
            logger.warning(f"保存AI对话历史失败: {str(e)}")


class WorkflowGenerationStrategy(CodeGenerationStrategy):
    """LangGraph 工作流生成路径（chat_history_save 节点自动持久化，on_done 为空实现）"""

    def __init__(self, app_id: Optional[int] = None):
        self.app_id = app_id

    def generate(self, prompt: str, user_id: int, **kwargs):
        from backend.app.services.graph.workflow_graph import run_workflow_streaming
        for kind, *payload in run_workflow_streaming(
                original_prompt=prompt,
                app_id=self.app_id,
                user_id=user_id,
        ):
            if kind == "stream":
                event_type, data = payload
                yield event_type, data

    def on_done(self, chunks: list[tuple[str, dict]], app_id: int, user_id: int, prompt: str):
        pass  # chat_history_save 节点已处理

    def on_error(self, error: Exception, chunks: list[tuple[str, dict]], app_id: int, user_id: int, prompt: str) -> str:
        logger.error(f"[workflow] 工作流执行异常: {str(error)}, app_id={app_id}")
        return "AI 暂时不能回答这个问题"


def get_streaming_generator(use_graph: bool, **init_kwargs) -> CodeGenerationStrategy:
    """策略工厂：根据 use_graph 返回对应的 Strategy 实例

    Args:
        use_graph: True 用 LangGraph，False 用 Facade 路径
        init_kwargs: 传给具体 Strategy 构造函数的参数
                    FacadeGenerationStrategy 需要: app_id, code_gen_type
                    WorkflowGenerationStrategy 需要: app_id (可选)
    """
    if use_graph:
        return WorkflowGenerationStrategy(app_id=init_kwargs.get('app_id'))
    else:
        code_gen_type = init_kwargs.get('code_gen_type')
        app_id = int(init_kwargs.get('app_id'))
        if not app_id or not code_gen_type:
            raise BusinessException(ErrorCode.MISSING_PARAMETER, "app_id和code_gen_type不能为空")
        if not CodeFileType.is_valid_file_type(code_gen_type):
            raise BusinessException(ErrorCode.INVALID_PARAMETER, "code_gen_type无效")
        if app_id <= 0:
            raise BusinessException(ErrorCode.INVALID_PARAMETER, "app_id必须大于0")
        return FacadeGenerationStrategy(
            app_id=app_id,
            code_gen_type=CodeFileType(code_gen_type),
        )
