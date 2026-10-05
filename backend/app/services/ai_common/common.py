from typing import Optional, Dict, Any


class StreamChunk:
    """
    流式响应数据块

    chunk_type 字段说明前端应该怎么渲染：
        "text"        —— 普通对话文本，用 Markdown/纯文本渲染（默认值）
        "tool_start"  —— 工具开始调用，前端可以渲染「工具调用卡片」的标题部分
        "tool_end"    —— 工具执行完毕，前端可以更新「工具调用卡片」为完成状态
        "error"       —— 错误信息，前端可以用红色/警告样式渲染
        "done"        —— 整轮结束（is_last=True 的时候 chunk_type=done）
        "code_updated" —— 代码已更新，前端可以刷新预览区域
        "code_review_start" —— 代码审核开始，前端可以显示「正在检视代码」
        "code_review_end" —— 代码审核结束，前端可以显示「代码检视完成」

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
    CODE_UPDATED = "code_updated"
    CODE_REVIEW_START = "code_review_start"
    CODE_REVIEW_END = "code_review_end"

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


def _compose_task_info(chunk: StreamChunk) -> dict:
    """
    组合任务信息，包含 task_id, info, extra
    """
    return {'task_id': chunk.metadata.get("tool_call_id"),
            'info': chunk.content,
            "extra": chunk.metadata}


def process_sse_chunk(chunk: StreamChunk):
    """
    处理流式响应，根据需要进行转换或过滤，简化 Chunk 内容
    将 AI 的回复分为即时立刻回复和耗时任务的回复
    即时立刻回复：直接返回给前端，例如普通文本
    耗时任务回复：包含 start 和 end 两个阶段，例如文件写入，网络搜索等

    :param chunk: 流式响应块
    :return: SSE 相应数据中 event 字段的类型，以及 data 字段的内容（由调用者封装正确格式）
    """
    msg_type = chunk.chunk_type
    if msg_type == StreamChunk.TYPE_TEXT:
        return 'message', {"d": chunk.content}
    # 不同的耗时任务返回提示信息
    # 返回 task_id 是唯一任务标识，用于区分多个不同耗时任务并行调用
    # chunk.content是前端需要展示的信息，extra是其他元数据，可以内部进行一定处理（界面上不呈现）
    elif msg_type == StreamChunk.TYPE_TOOL_START:  # 请求工具调用
        return 'task_start', _compose_task_info(chunk)
    elif msg_type == StreamChunk.TYPE_TOOL_END:  # 工具调用结束
        return 'task_end', _compose_task_info(chunk)
    elif msg_type == StreamChunk.TYPE_WEB_SEARCH:  # 网络搜索
        return 'web_search', _compose_task_info(chunk)
    elif msg_type == StreamChunk.TYPE_WEB_SEARCH_DONE:  # 网络搜索完成
        return 'web_search_done', _compose_task_info(chunk)
    elif msg_type == StreamChunk.CODE_UPDATED:  # 代码已更新
        return 'code_updated', {}
    else:
        return 'error', {"d": chunk.content or "AI 无任何响应，请检查 API_KEY 或者网络连接"}
