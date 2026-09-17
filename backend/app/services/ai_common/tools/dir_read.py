import json
import logging
import os.path
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.ai_common.tools import register_tool_display, to_absolute, to_relative, _ROOT_PATH
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context

TOOL_NAME = "目录读取工具"

# 应该忽略的文件名（精确匹配，不含路径）
IGNORE_FILES = [
    # 环境 / 配置
    '.env', '.env.local', '.env.*.local', '.gitignore', '.gitattributes',
    # 日志 / 临时
    '.log', '.tmp', '.temp', '.bak', '.old',
    # 系统
    '.DS_Store', 'Thumbs.db',
    # Node
    '.npmrc', '.yarnrc', '.yarnrc.yml',
]

# 应该忽略的文件夹（精确匹配目录名，不含路径）
IGNORE_FOLDERS = [
    # 依赖 / 包管理
    'node_modules', '.pnpm-store', '.yarn',
    # 构建产物
    'dist', 'build', '.next', '.nuxt', '.output', '.cache', '.parcel-cache', 'target',
    # Git / 版本控制
    '.git',
    # Python
    '__pycache__', '.venv', 'venv', '.tox', '.mypy_cache', '.pytest_cache',
    # IDE / 编辑器
    '.idea', '.vscode', '.eclipse', '.settings',
    # 其他
    'coverage', '.turbo', '.pnpm-store',
]

# 应该忽略的文件扩展名（小写，含点号）
IGNORE_EXTENSIONS = [
    '.log', '.tmp', '.temp', '.bak', '.old', '.cache',
    '.pyc', '.pyo', '.pyd',
    '.o', '.obj', '.exe', '.dll', '.so', '.dylib', '.class', '.jar', '.war',
    '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.avif',
    '.mp3', '.mp4', '.wav', '.flac', '.mov', '.avi', '.wmv',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.db', '.sqlite', '.sqlite3',
    '.psd', '.ai',
]


def _is_ignored(path: str) -> bool:
    """
    检查路径是否应被忽略。

    规则：
        - 若是目录：目录名（basename 部分，不区分大小写）在 IGNORE_FOLDERS 中则忽略
        - 若是文件：文件的 basename 在 IGNORE_FILES 中，或扩展名在 IGNORE_EXTENSIONS 中则忽略
    """
    import fnmatch

    name = os.path.basename(os.path.normpath(path))
    if not name:
        return False

    # 目录 / 文件夹命中
    if os.path.isdir(path):
        if name.lower() in {f.lower() for f in IGNORE_FOLDERS}:
            return True
        return False

    # 文件命中：精确匹配 + fnmatch 通配匹配 + 扩展名匹配
    if name in IGNORE_FILES:
        return True
    for pattern in IGNORE_FILES:
        if any(ch in pattern for ch in '*?[') and fnmatch.fnmatch(name, pattern):
            return True

    ext = os.path.splitext(name)[1].lower()
    if ext in IGNORE_EXTENSIONS:
        return True

    return False


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

    for name in entries:
        full_path = os.path.join(abs_path, name)
        if _is_ignored(full_path):
            continue

        if os.path.isdir(full_path):
            sub_rel = to_relative(full_path)
            node['children'].append(get_tree(sub_rel))  # 递归
        elif os.path.isfile(full_path):
            file_rel = to_relative(full_path)
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
        if _is_ignored(os.path.join(root_path, file)):
            continue
        node['children'].append({
            'name': file,
            'type': 'file',
            'path': to_relative(os.path.join(root_path, file)),
            'children': None,
        })
    return node


@tool(
    name_or_callable=TOOL_NAME,
    description='目录读取工具，用于读取指定路径下的所有文件和子目录，返回 JSON 格式字符串描述的目录树，格式如下（示例 读取/src目录）：'
                '{"name": "src", "type": "folder", "path": "src", "children": '
                '[{"name": "src/pages", "type": "folder", "path": "src/pages", "children": '
                '[{"name": "Dashboard.vue", "type": "file", "path": "src/pages/Dashboard.vue", "children": null}, '
                '{"name": "Members.vue", "type": "file", "path": "src/pages/Members.vue", "children": null}, '
                '{"name": "Tasks.vue", "type": "file", "path": "src/pages/Tasks.vue", "children": null}'
                ']}, '
                '{"name": "src/router", "type": "folder", "path": "src/router", "children": '
                '[{"name": "index.js", "type": "file", "path": "src/router/index.js", "children": null}]}, '
                '{"name": "App.vue", "type": "file", "path": "src/App.vue", "children": null}]}',
    args_schema=DirReadToolArgs
)
def dir_read_tool(dir_path: str = "", recursive: bool = True) -> str:
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
        description='目录读取工具，用于读取指定路径下的所有文件和子目录，返回 JSON 格式字符串描述的目录树，格式如下（示例 读取/src目录）：'
                    '{"name": "src", "type": "folder", "path": "src", "children": '
                    '[{"name": "src/pages", "type": "folder", "path": "src/pages", "children": '
                    '[{"name": "Dashboard.vue", "type": "file", "path": "src/pages/Dashboard.vue", "children": null}, '
                    '{"name": "Members.vue", "type": "file", "path": "src/pages/Members.vue", "children": null}, '
                    '{"name": "Tasks.vue", "type": "file", "path": "src/pages/Tasks.vue", "children": null}'
                    ']}, '
                    '{"name": "src/router", "type": "folder", "path": "src/router", "children": '
                    '[{"name": "index.js", "type": "file", "path": "src/router/index.js", "children": null}]}, '
                    '{"name": "App.vue", "type": "file", "path": "src/App.vue", "children": null}]}',
        args_schema=DirReadToolArgs
    )
    def _tool(dir_path: str = "", recursive: bool = True) -> str:
        context = get_runtime_context()
        app_id = context.get("app_id")
        if not app_id:
            logging.error("app_id 未设置")
            return f"目录读取失败，app_id 未设置"
        if not recursive:
            root_path = os.path.join(Path(_ROOT_PATH), f"vue_project_{app_id}", dir_path)
            return json.dumps(_file_names_in_this_dir(root_path))
        else:
            root_path = os.path.join(f"vue_project_{app_id}", dir_path)
            return json.dumps(get_tree(root_path))

    return _tool


def _show_start() -> str:
    return f"\n\n开始读取目录...\n\n"


def _show_end(args: dict, result: str, success: bool) -> str:
    dir_path = args.get("dir_path") or "项目根目录"
    if success:
        return f"\n\n✅ 读取目录: `{dir_path}` 完成 \n\n"
    return f"\n\n❌ 读取目录失败 \n\n"


register_tool_display(
    tool_name=TOOL_NAME,
    show_start=_show_start,
    show_end=_show_end,
)
