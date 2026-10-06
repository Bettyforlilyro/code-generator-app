# 定义 Graph 全局状态
from typing import Literal, Optional, Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict

from backend.app.common.enums import CodeFileType
from backend.app.schemas.responses import BaseCodeResult
from backend.app.services.ai_common import StreamChunk
from backend.app.services.graph.model import (
    ImageResource,
    merge_image_list,
    merge_generated_code
)


class WorkflowState(TypedDict, total=False):
    """
    Graph 全局状态
    
    说明：
    - 使用 total=False 让所有字段都是可选的，便于节点按需更新
    - 带 Annotated reducer 的字段（messages / image_list）会自动合并，其他字段直接覆盖
    """
    
    # ========== 输入上下文 ==========
    # 会话历史和上下文记忆（带 reducer：自动追加）
    messages: Annotated[list[AnyMessage], add_messages]
    history_ai_message_len: int
    # 用户原始输入
    original_prompt: str
    # 关联的应用 ID（用于文件保存、对话历史持久化等）
    app_id: int
    # 用户 ID（写对话历史 DB 需要）
    user_id: int

    # ========== 任务规划阶段 ==========
    # 增强提示词（task_evaluate 输出）
    enhanced_prompt: str
    # 任务类型标识
    task_type: Literal["chat", "new_build", "modify"]
    # 图片素材和资源（带 reducer：覆盖 LOGO/ARCHITECTURE，追加 CONTENT/ILLUSTRATION）
    image_list: Annotated[list[ImageResource], merge_image_list]
    
    # ========== 代码生成阶段 ==========
    # 代码生成类型
    code_gen_type: CodeFileType
    # 代码生成结果的结构化数据，或者修改回复/问题回复（文本），内部处理
    generate_output: Annotated[str | BaseCodeResult, merge_generated_code]

    # ========== 流式透传通道 ==========
    # code_generator 节点流式执行时透传的原始 StreamChunk
    # 外层 run_workflow_streaming() 拿到后统一调 processed_chunk() 转前端格式
    # （避免节点里手动判断 chunk 类型丢失原始信息）
    streaming_chunk: Optional[StreamChunk]

    # ========== 代码审查阶段 ==========
    # 重试次数（防止审查无限循环）
    retry_count: int
    # 代码审查 Agent 的反馈（不通过时的修复建议）
    qa_feedback: Optional[str]
    # 代码审查是否通过
    qa_pass: bool
    
    # ========== 最终输出 ==========
    # 生成代码的保存路径
    code_save_path: str
    # ========= 调试保留字段 ========
    # 当前执行节点（用于调试/监控）
    # 加 last_wins reducer：并行节点同时更新时取后执行的值，串行时就是普通覆盖
    current_node: Annotated[str, lambda old, new: new]
    # 错误信息（用于调试）
    error_info: Annotated[str, lambda old, new: new]
