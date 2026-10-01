import fnmatch
import json
import logging
import os.path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.ai_common.tools import (
    register_tool_display, to_absolute, to_relative, to_app_absolute,
    _normalize_rel_path, DIR_READ_TOOL_NAME,
)
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context

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


def _to_root_absolute(rel_path: str) -> str:
    """
    把内部相对路径转成以 "/" 开头的伪绝对路径，对 LLM 透明。

    示例规则：
      - 空串或 "."           -> "/"（项目根）
      - "src/App.vue"        -> "/src/App.vue"
      - "/src/App.vue"       -> "/src/App.vue"（已带前缀，保持不变）
      - "\\src\\App.vue"    -> "/src/App.vue"（Windows 分隔符也规整）
    """
    if not rel_path or rel_path == ".":
        return "/"
    normalized = rel_path.replace("\\", "/")
    cleaned = normalized.lstrip("/")
    return "/" + cleaned


def _is_ignored(path: str) -> bool:
    """
    检查路径是否应被忽略。

    规则：
        - 若是目录：目录名（basename 部分，不区分大小写）在 IGNORE_FOLDERS 中则忽略
        - 若是文件：文件的 basename 在 IGNORE_FILES 中，或扩展名在 IGNORE_EXTENSIONS 中则忽略
    """
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
    dir_path: str = Field(description="目录的根路径，如果不填或者为'/'表示默认读取根路径", default="")
    recursive: bool = Field(description="是否需要递归读取子目录，默认True，如果为False，只读取当前目录下的文件，子目录会忽略", default=True)


def get_tree(rel_path: str = '') -> dict:
    """
    递归读取目录结构（相对于 ROOT_PATH）。

    参数:
        rel_path: 基于 ROOT_PATH 的相对路径，例如 'docs' 或 'docs/sub'
                  传 '' 表示根目录本身
    返回:
        嵌套字典，所有 node 的 path 都以 "/" 开头（对 LLM 透明），
        name 字段保持原样（用于在 children 中展示当前节点名）。
    """
    abs_path = to_absolute(rel_path)
    if not os.path.isdir(abs_path):
        raise NotADirectoryError(f"路径不存在或不是文件夹: {rel_path}")

    node = {
        'name': name_for_display(to_relative(abs_path)),
        'type': 'folder',
        'path': _to_root_absolute(to_relative(abs_path)),
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
                'path': _to_root_absolute(file_rel),
                'children': None,
            })

    return node


def name_for_display(rel_path: str) -> str:
    """
    为根节点生成有意义的 name 展示值。
    - 如果 rel_path 本身就是项目根（空串 / "."），返回 "/"。
    - 否则返回 rel_path 的最后一段目录名。

    这样根节点 name 不会出现 ""，在 JSON 里可读性更好。
    """
    if not rel_path or rel_path == ".":
        return "/"
    return os.path.basename(rel_path.replace(os.sep, "/"))


def _file_names_in_this_dir(root_path: str):
    """
    读取当前目录（绝对路径）下的所有文件名。
    返回的 node.path 统一以 "/" 开头。
    """
    parent_rel = to_relative(root_path)
    node = {
        'name': name_for_display(parent_rel),
        'type': 'folder',
        'path': _to_root_absolute(parent_rel),
        'children': [],
    }
    for file in os.listdir(root_path):
        full = os.path.join(root_path, file)
        if _is_ignored(full):
            continue
        node['children'].append({
            'name': file,
            'type': 'file',
            'path': _to_root_absolute(to_relative(full)),
            'children': None,
        })
    return node


@tool(
    name_or_callable=DIR_READ_TOOL_NAME,
    description='目录读取工具，用于读取指定路径下的所有文件和子目录，返回 JSON 格式字符串描述的目录树，格式如下（示例 读取/src目录）：'
                '{"name": "src", "type": "folder", "path": "/src", "children": '
                '[{"name": "pages", "type": "folder", "path": "/src/pages", "children": '
                '[{"name": "Dashboard.vue", "type": "file", "path": "/src/pages/Dashboard.vue", "children": null}, '
                '{"name": "Members.vue", "type": "file", "path": "/src/pages/Members.vue", "children": null}, '
                '{"name": "Tasks.vue", "type": "file", "path": "/src/pages/Tasks.vue", "children": null}'
                ']}, '
                '{"name": "router", "type": "folder", "path": "/src/router", "children": '
                '[{"name": "index.js", "type": "file", "path": "/src/router/index.js", "children": null}]}, '
                '{"name": "App.vue", "type": "file", "path": "/src/App.vue", "children": null}]}',
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
        tree = get_tree(dir_path)
        # 根路径名转换成 /
        tree["name"] = "/" if not dir_path or dir_path == "." or dir_path == '/' else tree["name"]
        return json.dumps(tree)


def _strip_app_prefix(tree: dict, prefix: str) -> dict:
    """
    递归剥离目录树中 path/name 字段的 app 内部前缀，保留 "/" 前缀。

    get_tree / _file_names_in_this_dir 返回的 path 已经是
    "/vue_project_123/src/App.vue" 这样的形式（带 "/" 前缀），
    这里把 "/vue_project_{app_id}" 整段剥掉，得到 "/src/App.vue"。

    根节点如果剥离后 path 为空，则置为 "/"（项目根）。
    """
    # prefix 形如 'vue_project_123'，path 形如 '/vue_project_123/...'
    prefix_slash = "/" + prefix           # '/vue_project_123'
    prefix_slash_sep = prefix_slash + "/"  # '/vue_project_123/'
    prefix_win_sep = prefix_slash + os.sep

    def _strip(value: str) -> str:
        if not value:
            return value
        if value.startswith(prefix_slash_sep):
            stripped = value[len(prefix_slash_sep):]
        elif value.startswith(prefix_win_sep):
            stripped = value[len(prefix_win_sep):]
        elif value == prefix_slash:
            stripped = "/"   # 剥完就是项目根
        else:
            return value
        # 再保证有 "/" 开头（如果剥离后是空串也保持根语义）
        if not stripped or stripped == ".":
            return "/"
        return "/" + stripped.lstrip("/\\")

    result = {k: (_strip(v) if isinstance(v, str) else v) for k, v in tree.items()}
    if result.get("children"):
        result["children"] = [_strip_app_prefix(child, prefix) for child in result["children"]]
    return result


def dir_read_tool_with_context():
    """
    工厂函数：返回一个 LLM 可调用的闭包工具，每次执行时从 context_var 读取当前请求的 context
    """

    @tool(
        name_or_callable=DIR_READ_TOOL_NAME,
        description='目录读取工具，用于读取指定路径下的所有文件和子目录，返回 JSON 格式字符串描述的目录树，格式如下（示例 读取/src目录）：'
                    '{"name": "src", "type": "folder", "path": "/src", "children": '
                    '[{"name": "pages", "type": "folder", "path": "/src/pages", "children": '
                    '[{"name": "Dashboard.vue", "type": "file", "path": "/src/pages/Dashboard.vue", "children": null}, '
                    '{"name": "Members.vue", "type": "file", "path": "/src/pages/Members.vue", "children": null}, '
                    '{"name": "Tasks.vue", "type": "file", "path": "/src/pages/Tasks.vue", "children": null}'
                    ']}, '
                    '{"name": "router", "type": "folder", "path": "/src/router", "children": '
                    '[{"name": "index.js", "type": "file", "path": "/src/router/index.js", "children": null}]}, '
                    '{"name": "App.vue", "type": "file", "path": "/src/App.vue", "children": null}]}',
        args_schema=DirReadToolArgs
    )
    def _tool(dir_path: str = "", recursive: bool = True) -> str:
        context = get_runtime_context()
        app_id = context.get("app_id")
        if not app_id:
            logging.error("app_id 未设置")
            return "目录读取失败，app_id 未设置"

        app_rel_prefix = f"vue_project_{app_id}"

        if not recursive:
            abs_path = to_app_absolute(app_id, dir_path)
            tree = _file_names_in_this_dir(abs_path)
        else:
            # 拼出 ROOT_PATH 下的相对路径，交给 get_tree 内部 to_absolute 处理
            root_for_get_tree = os.path.join(app_rel_prefix, _normalize_rel_path(dir_path)) \
                if _normalize_rel_path(dir_path) else app_rel_prefix
            tree = get_tree(root_for_get_tree)

        # 剥离 vue_project_{app_id} 内部前缀，对 LLM 透明
        tree = _strip_app_prefix(tree, app_rel_prefix)
        # 根路径名转换成 /
        tree["name"] = "/" if not dir_path or dir_path == "." or dir_path == '/' else tree["name"]
        return json.dumps(tree)

    return _tool


def _show_start() -> str:
    return f"\n\n开始读取目录...\n\n"


def _show_end(args: dict, result: str, success: bool) -> str:
    dir_path = args.get("dir_path") or "项目根目录"
    if success:
        return f"\n\n✅ 读取目录: `{dir_path}` 完成 \n\n"
    return f"\n\n❌ 读取目录失败 \n\n"


register_tool_display(
    tool_name=DIR_READ_TOOL_NAME,
    show_start=_show_start,
    show_end=_show_end,
)
