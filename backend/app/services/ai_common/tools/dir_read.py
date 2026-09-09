import json
import logging
import os.path
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.ai_common.tools import register_tool_display, to_absolute, to_relative, _ROOT_PATH
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context

TOOL_NAME = "目录读取工具"


class DirReadToolArgs(BaseModel):
    dir_path: str = Field(description="目录的根路径，如果不填默认读取根路径", default="")
    recursive: bool = Field(description="是否需要递归读取子目录，默认True，如果为False，只读取当前目录下的文件，子目录会忽略", default=True)


def get_tree(rel_path: str = '') -> dict:
    """
    递归读取目录结构（相对于 ROOT_PATH）。

    参数:
        rel_path: 基于 ROOT_PATH 的相对路径，例如 'docs' 或 'docs/sub'
                  传 '' 表示根目录本身
    返回:
        嵌套字典，name 和 path 均为基于 ROOT_PATH 的相对路径
    """
    abs_path = to_absolute(rel_path)
    if not os.path.isdir(abs_path):
        raise NotADirectoryError(f"路径不存在或不是文件夹: {rel_path}")

    # 根节点的 name 为相对路径本身
    root_name = to_relative(abs_path)

    node = {
        'name': root_name,
        'type': 'folder',
        'path': root_name,
        'children': [],
    }

    entries = sorted(os.listdir(abs_path))
    folders = [e for e in entries if os.path.isdir(os.path.join(abs_path, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(abs_path, e))]

    for name in folders:
        sub_rel = to_relative(os.path.join(abs_path, name))
        node['children'].append(get_tree(sub_rel))  # 递归

    for name in files:
        file_rel = to_relative(os.path.join(abs_path, name))
        node['children'].append({
            'name': name,
            'type': 'file',
            'path': file_rel,
            'children': None,
        })

    return node


def _file_names_in_this_dir(root_path: str):
    """
    读取当前目录（绝对路径）下的所有文件名
    """
    node = {
        'name': to_relative(root_path),
        'type': 'folder',
        'path': to_relative(root_path),
        'children': [],
    }
    # 非递归读取当前目录下的所有文件
    for file in os.listdir(root_path):
        node['children'].append({
            'name': file,
            'type': 'file',
            'path': to_relative(os.path.join(root_path, file)),
            'children': None,
        })
    return node


@tool(
    name_or_callable=TOOL_NAME,
    description="目录读取工具，用于读取指定路径下的所有文件和子目录，返回 JSON 格式字符串描述的目录树",
    args_schema=DirReadToolArgs
)
def dir_read_tool(dir_path: str, recursive: bool) -> str:
    """
    读取指定路径下的所有文件和子目录
    返回 JSON 格式字符串描述的目录树
    """
    if not recursive:
        root_path = to_absolute(dir_path)
        return json.dumps(_file_names_in_this_dir(root_path))
    else:
        return json.dumps(get_tree(dir_path))


def dir_read_tool_with_context():
    """
    工厂函数：工厂函数：返回一个 LLM 可调用的闭包工具，每次执行时从 context_var 读取当前请求的 context
    """

    @tool(
        name_or_callable=TOOL_NAME,
        description="目录读取工具，用于读取指定路径下的所有文件和子目录，返回 JSON 格式字符串描述的目录树",
        args_schema=DirReadToolArgs
    )
    def _tool(dir_path: str, recursive: bool) -> str:
        context = get_runtime_context()
        app_id = context.get("app_id")
        if not app_id:
            logging.error("app_id 未设置")
            return f"目录读取失败，app_id 未设置"
        if not recursive:
            root_path = os.path.join(Path(_ROOT_PATH), f"vue_project_{app_id}", dir_path)
            return json.dumps(_file_names_in_this_dir(root_path))
        else:
            return json.dumps(get_tree(dir_path))

    _tool.name = TOOL_NAME

    return _tool


def _show_start() -> str:
    return f"开始读取目录...\n"


def _show_end(args: dict, result: str, success: bool) -> str:
    dir_path = args.get("dir_path")
    if success and "读取成功" in result and dir_path:
        return f"✅ 读取目录: `{dir_path}` 完成 \n\n"
    return f"❌ 读取目录失败 \n\n"


register_tool_display(
    tool_name=TOOL_NAME,
    show_start=_show_start,
    show_end=_show_end,
)
