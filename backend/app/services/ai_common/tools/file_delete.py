import logging
import os.path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.ai_common.tools import to_absolute, register_tool_display
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context

TOOL_NAME = "文件删除工具"


class FileDeleteToolArgs(BaseModel):
    file_path: str = Field(description="需要删除的文件的路径")


@tool(
    name_or_callable=TOOL_NAME,
    description="删除指定路径的文件",
    args_schema=FileDeleteToolArgs,
)
def file_delete_tool(file_path: str) -> str:
    """
    删除指定路径的文件。
    """
    abs_path = to_absolute(file_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    os.remove(abs_path)
    return f"文件 {file_path} 已成功删除"


def file_delete_tool_with_context():
    """
    工厂函数：工厂函数：返回一个 LLM 可调用的闭包工具，每次执行时从 context_var 读取当前请求的 context
    """
    @tool(
        name_or_callable=TOOL_NAME,
        description="删除指定路径的文件",
        args_schema=FileDeleteToolArgs,
    )
    def _tool(file_path: str) -> str:
        """
        删除指定路径的文件。
        """
        context = get_runtime_context()
        app_id = context.get("app_id")
        if not app_id:
            logging.error("app_id 未设置")
            return "app_id 未设置，删除失败"
        real_path = os.path.join(f"vue_project_{app_id}", file_path)
        abs_path = to_absolute(real_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        os.remove(abs_path)
        return f"文件 {file_path} 已成功删除"

    _tool.name = TOOL_NAME

    return _tool


def _show_start() -> str:
    """
    显示开始删除文件的提示。
    """
    return f"开始删除文件......"


def _show_end(args: dict, result: str, success: bool) -> str:
    """
    显示删除文件的提示。
    """
    file_path = args.get("file_path")
    if success and file_path:
        return f"✅ 删除文件: `{file_path}` 已成功删除"
    else:
        return f"❌ 删除文件失败"


register_tool_display(
    tool_name=TOOL_NAME,
    show_start=_show_start,
    show_end=_show_end,
)

