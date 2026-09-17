import logging
import os.path
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT
from backend.app.services.ai_common.tools import register_tool_display, FILE_WRITE_TOOL_NAME
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context


class FileWriteToolArgs(BaseModel):
    file_path: str = Field(description="文件的相对路径")
    content: str = Field(description="要写入的内容")


# ---------------------------------------------------------------------------
# 方式 A：无状态版本（不需要 context，会被 get_all_tools_in_module 自动收集）
# ---------------------------------------------------------------------------
@tool(
    name_or_callable=FILE_WRITE_TOOL_NAME,
    description="文件写入工具，用于将内容写入指定路径下的指定文件，如果文件已存在，则覆盖写入",
    args_schema=FileWriteToolArgs
)
def file_write_tool(file_path: str, content: str) -> str:
    relative_path = Path(file_path)
    full_path = Path(os.path.join(Path(DEFAULT_GENERATE_ROOT), "test")) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return f"文件写入成功，文件路径：{relative_path}"


def file_write_tool_with_context():
    """
    工厂函数：工厂函数：返回一个 LLM 可调用的闭包工具，每次执行时从 context_var 读取当前请求的 context
    """

    @tool(
        name_or_callable=FILE_WRITE_TOOL_NAME,
        description="文件写入工具，用于将内容写入指定路径下的指定文件，如果文件已存在，则覆盖写入",
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

    return _tool


# ---- 本文件的工具注册自定义展示方法，调用一次即可，key 都是 TOOL_NAME ----
def _show_start() -> str:
    """
    工具开始调用时怎么展示——显示文件路径和内容摘要
    :return: 展示的字符串
    """
    return f"\n\n📝 AI 正在奋力编码ing...\n\n"


def _show_end(args, result, success) -> str:
    """
    工具结束时怎么展示——显示文件路径和状态
    :param args: 工具调用时的参数
    :param result: 工具调用返回值
    :param success: 是否成功
    :return: 展示的字符串
    """
    file_path = args.get("file_path")
    content = args.get("content")
    size = len(content.encode("utf-8"))
    if size > 1024 * 1024:
        size_human_friendly = f"{size / 1024 / 1024:.2f} MB"
    elif size > 1024:
        size_human_friendly = f"{size / 1024:.2f} KB"
    else:
        size_human_friendly = f"{size} B"
    if success and "写入成功" in result and file_path:
        return f"\n\n✅ 已生成代码并存入文件: `{file_path}` ，大小: {size_human_friendly} \n\n"
    return f"\n\n❌ 代码写入失败！ \n\n"


def preview(args: dict) -> str:
    # TODO 本项目中暂时使用固定的预览URL，如果后续部署到生产环境，需要根据实际情况修改
    context = get_runtime_context()
    app_id = context.get("app_id")
    if not app_id:
        logging.error("app_id 未设置")
        return ""
    file_path = args.get("file_path")
    return f"http://localhost:5000/api/v1/code/preview/{app_id}/{file_path}"


register_tool_display(
    tool_name=FILE_WRITE_TOOL_NAME,
    show_start=_show_start,
    show_end=_show_end,
    preview=preview,
)
