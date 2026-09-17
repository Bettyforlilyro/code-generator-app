import logging
import os.path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.ai_common.tools import register_tool_display, to_absolute
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context

TOOL_NAME = "文件读取工具"


class FileReadToolArgs(BaseModel):
    file_path: str = Field(description="需要读取的文件的路径")


@tool(
    name_or_callable=TOOL_NAME,
    description="读取文件内容，用于读取指定路径文件的内容",
    args_schema=FileReadToolArgs,
)
def file_read_tool(file_path: str) -> str:
    """
    读取文件内容，用于读取指定路径文件的内容。
    """
    abs_path = to_absolute(file_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"【{abs_path}】文件不存在")
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"读取文件失败: {e}")
        return f"文件读取失败，错误信息: {e}"


def file_read_tool_with_context():
    """
    工厂函数：工厂函数：返回一个 LLM 可调用的闭包工具，每次执行时从 context_var 读取当前请求的 context
    """

    @tool(
        name_or_callable=TOOL_NAME,
        description="读取文件内容，用于读取指定路径文件的内容",
        args_schema=FileReadToolArgs,
    )
    def _tool(file_path: str) -> str:
        context = get_runtime_context()
        app_id = context.get("app_id")
        if not app_id:
            logging.error("app_id 未设置")
            return f"文件读取失败，app_id 未设置"
        real_path = os.path.join(f"vue_project_{app_id}", file_path)
        abs_path = to_absolute(real_path)
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logging.error(f"读取文件失败: {e}")
            return f"文件读取失败，错误信息: {e}"

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
    if not file_path:
        return "\n\n❌ 文件路径不存在，读取失败\n\n"
    if not success:
        return "\n\n❌ 读取文件失败\n\n"
    return f"\n\n✅ 读取文件: `{file_path}` 完成\n\n"


register_tool_display(
    tool_name=TOOL_NAME,
    show_start=_show_start,
    show_end=_show_end,
)
