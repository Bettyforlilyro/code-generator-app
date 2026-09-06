import logging
import os.path
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context

TOOL_NAME = "文件写入工具"


class FileWriteToolArgs(BaseModel):
    file_path: str = Field(description="文件的相对路径")
    content: str = Field(description="要写入的内容")


# ---------------------------------------------------------------------------
# 方式 A：无状态版本（不需要 context，会被 get_all_tools_in_module 自动收集）
# ---------------------------------------------------------------------------
@tool(
    description="文件写入工具，用于将内容写入指定路径下的指定文件",
    args_schema=FileWriteToolArgs
)
def file_write_tool(file_path: str, content: str) -> str:
    relative_path = Path(file_path)
    full_path = Path(os.path.join(Path(DEFAULT_GENERATE_ROOT), "test")) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return f"文件写入成功，文件路径：{relative_path}"


file_write_tool.name = TOOL_NAME


def file_write_tool_with_context():
    """
    工厂函数：工厂函数：返回一个 LLM 可调用的闭包工具，每次执行时从 context_var 读取当前请求的 context
    """

    @tool(
        description="文件写入工具，用于将内容写入指定路径下的指定文件",
        args_schema=FileWriteToolArgs
    )
    def _tool(file_path: str, content: str) -> str:
        # 被调用时获取上下文参数
        context = get_runtime_context()
        app_id = context.get("app_id")
        if not app_id:
            logging.error("app_id 未设置")
            return f"文件写入失败，app_id 未设置"
        try:
            relative_path = Path(file_path)
            # 把相对路径转换为绝对路径
            if not relative_path.is_absolute():
                full_dir_name = f"vue_project_{app_id}"
            else:
                return f"文件写入失败，路径参数只能输入相对路径！"
            full_path = Path(os.path.join(DEFAULT_GENERATE_ROOT, full_dir_name)) / relative_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return f"文件写入成功，文件路径：{relative_path}"
        except Exception as e:
            logging.error(f"文件写入失败：{e}")
            return f"文件写入失败，错误信息：{e}"

    _tool.name = TOOL_NAME
    return _tool
