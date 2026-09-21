# 定义 Graph 全局状态
from typing import Literal, Optional, List, Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState, add_messages
from typing_extensions import TypedDict

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.services.graph.model.image_resource import ImageResource, merge_image_list


class WorkflowState(TypedDict):
    # 会话历史和上下文记忆
    messages: Annotated[list[AnyMessage], add_messages]
    # 用户原始输入
    original_prompt: str
    # 当前执行节点
    current_node: str
    # 增强提示词
    enhanced_prompt: str
    # 任务类型标识
    task_type: Literal["chat", "new_build", "modify"]
    # 代码生成类型
    code_gen_type: CodeFileType
    # 图片素材和资源，自定义合并逻辑（因为可能是更新部分图片素材，也可能是初次搜索所有图片素材，节点内部 Agent 根据 State 判断
    image_list: Annotated[list[ImageResource], merge_image_list]
    # 生成代码的保存路径
    code_save_path: str
    # 项目构建成功的路径
    build_success_path: str
    # 重试次数，防止一直审查不通过修改
    retry_count: int
    # 代码审查 Agent 的反馈
    qa_feedback: Optional[str]
    # 代码审查是否通过
    qa_pass: bool
    # 错误信息，用于调试
    error_info: str
