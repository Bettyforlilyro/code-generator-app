import logging
import os.path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.ai_common.tools import (
    register_tool_display, to_absolute, to_app_absolute, FILE_READ_TOOL_NAME,
)
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context

_logger = logging.getLogger(__name__)


class FileReadToolArgs(BaseModel):
    file_path: str = Field(description="需要读取的文件的路径")


@tool(
    name_or_callable=FILE_READ_TOOL_NAME,
    description="读取文件内容，用于读取指定路径文件的内容",
    args_schema=FileReadToolArgs,
)
def file_read_tool(file_path: str) -> str:
    """
    读取文件内容，用于读取指定路径文件的内容。
    """
    abs_path = to_absolute(file_path)
    if not os.path.isfile(abs_path):
        return f"文件读取失败，文件不存在: {file_path}"
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        _logger.error(f"读取文件失败 [{file_path}]: {e}")
        return f"文件读取失败: {file_path}"


def file_read_tool_with_context():
    """
    工厂函数：工厂函数：返回一个 LLM 可调用的闭包工具，每次执行时从 context_var 读取当前请求的 context
    """

    @tool(
        name_or_callable=FILE_READ_TOOL_NAME,
        description="读取文件内容，用于读取指定路径文件的内容",
        args_schema=FileReadToolArgs,
    )
    def _tool(file_path: str) -> str:
        context = get_runtime_context()
        app_id = context.get("app_id")
        if not app_id:
            _logger.error("app_id 未设置")
            return f"文件读取失败，app_id 未设置"
        try:
            abs_path = to_app_absolute(app_id, file_path)
        except ValueError as e:
            return f"文件读取失败，非法路径: {e}"
        if not os.path.isfile(abs_path):
            return f"文件读取失败，文件不存在: {file_path}"
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            _logger.error(f"读取文件失败 [{file_path}]: {e}")
            return f"文件读取失败: {file_path}"

    return _tool


def _show_start() -> str:
    """
    显示开始读取文件的提示信息
    """
    return f"\n\n开始读取文件......\n\n"


def _show_end(args: dict, result: str, success: bool) -> str:
    """
    显示读取文件的提示。
    """
    file_path = args.get("file_path")
    if not success:
        return "\n\n❌ 读取文件失败\n\n"
    return f"\n\n✅ 读取文件: `{file_path}` 完成\n\n"


register_tool_display(
    tool_name=FILE_READ_TOOL_NAME,
    show_start=_show_start,
    show_end=_show_end,
)
