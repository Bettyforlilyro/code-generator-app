import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import List, Dict, Callable

from langchain_core.tools import BaseTool

from backend.app.common.utils.cache import MemoryCache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 扫描结果缓存（进程生命周期内有效）
#   - ttl_seconds=0  永不过期（工具模块在程序运行期间不会变动）
#   - max_size=0     不限制容量
# ---------------------------------------------------------------------------
_scan_cache: MemoryCache[str, object] = MemoryCache(
    max_size=0, ttl_seconds=0
)

_CACHE_KEY_BASE_TOOLS = "__base_tools__"
_CACHE_KEY_FACTORIES = "__context_factories__"


# ---------------------------------------------------------------------------
# 通用工具发现逻辑
# ---------------------------------------------------------------------------

def _iter_tool_modules():
    """遍历 tools/ 包下所有业务模块（排除 __init__）"""
    package_path = Path(__file__).resolve().parent
    package_name = __name__
    for module_info in pkgutil.iter_modules([str(package_path)]):
        if module_info.name == "__init__":
            continue
        yield importlib.import_module(f"{package_name}.{module_info.name}")


def _collect_all_base_tools() -> List[BaseTool]:
    """
    扫描所有模块，收集通过 @tool 声明的 BaseTool 实例（无状态工具）。
    首次调用时扫描，后续直接从缓存返回。
    """
    cached = _scan_cache.get(_CACHE_KEY_BASE_TOOLS)
    if cached is not None:
        return cached

    tools: List[BaseTool] = []
    for module in _iter_tool_modules():
        for name, obj in inspect.getmembers(module):
            if name.startswith("_") or inspect.ismodule(obj):
                continue
            if isinstance(obj, BaseTool):
                tools.append(obj)

    result = _deduplicate_tools(tools)
    _scan_cache.set(_CACHE_KEY_BASE_TOOLS, result)
    logger.info(f"[tools] 扫描到 {len(result)} 个无状态工具: {[t.name for t in result]}")
    return result


def _collect_context_factories() -> Dict[str, Callable]:
    """
    扫描所有模块，收集生成带 context 工具的工厂函数。
    返回 {factory_name: factory_fn}。

    约定：工厂函数命名必须以 _with_context 结尾，
    例如 file_write_tool_with_context() -> BaseTool。
    这个后缀约定保证了不会误匹配其他包含 context 字样的普通函数。

    首次调用时扫描，后续直接从缓存返回。
    """
    cached = _scan_cache.get(_CACHE_KEY_FACTORIES)
    if cached is not None:
        return cached

    factories: Dict[str, Callable] = {}
    for module in _iter_tool_modules():
        for name, obj in inspect.getmembers(module):
            # 必须以 _with_context 结尾、不是私有、可调用
            if not name.endswith("_with_context"):
                continue
            if name.startswith("_"):
                continue
            if not callable(obj):
                continue
            factories[name] = obj

    _scan_cache.set(_CACHE_KEY_FACTORIES, factories)
    logger.info(f"[tools] 扫描到 {len(factories)} 个 context 工厂: {list(factories.keys())}")
    return factories


def _deduplicate_tools(tools: List[BaseTool]) -> List[BaseTool]:
    """按 tool.name 去重，保持顺序"""
    seen: set[str] = set()
    result: List[BaseTool] = []
    for t in tools:
        if t.name not in seen:
            seen.add(t.name)
            result.append(t)
    return result


# ---------------------------------------------------------------------------
# 缓存管理（主要用于开发热重载场景）
# ---------------------------------------------------------------------------

def invalidate_cache() -> None:
    """
    清除工具扫描缓存，下次调用时会重新扫描。

    主要用途：
        - 开发期间新增/修改了工具文件后，调用此函数让新代码生效
        - 测试中动态 mock 工具模块时

    生产环境一般不需要调——工具模块在启动后不会变动。
    """
    _scan_cache.clear()
    logger.info("[tools] 扫描缓存已清除，下次访问将重新扫描")


# ---------------------------------------------------------------------------
# 对外 API
# ---------------------------------------------------------------------------

def get_all_tools_in_module() -> List[BaseTool]:
    """
    获取所有模块中声明的无状态工具（不注入 context）。
    适合不需要运行时信息的纯函数工具。
    """
    return _collect_all_base_tools()


def get_tools_by_names(tool_names: List[str]) -> BaseTool | None:
    """按名称查找无状态工具，未找到返回 None"""
    for t in get_all_tools_in_module():
        if t.name in tool_names:
            return t
    return None


def tools_factory_with_context(tool_names: List[str] | None = None) -> List[BaseTool]:
    """
    通用工厂：扫描 tools/ 包下所有 *_with_context 工厂函数，返回生成的 BaseTool 列表。

    工作流程：
    1. 扫描所有以 _with_context 结尾的工厂函数
    2. 如果指定了 tool_names，按 tool.name 过滤（此时已是工具的显示名，
       例如 "文件写入工具"，而非工厂函数名）
    3. 去重后返回

    Args:
        tool_names: 可选，指定只生成哪些工具（按 tool.name 匹配）；
                   为 None 时生成全部带 _with_context 的工具

    Returns:
        生成好的 BaseTool 列表

    使用约定：
        每个工具文件应同时提供两个版本：
        - @tool 装饰的无状态版本（会被 get_all_tools_in_module 收集）
        - xxx_with_context() 工厂函数（会被本函数收集）
        两者的 tool.name 必须一致，这样 builder 侧可以用同一个名字
        在无状态 / 带 context 两个版本间切换。
    """
    factories = _collect_context_factories()

    generated: List[BaseTool] = []
    for _factory_name, factory_fn in factories.items():
        tool = factory_fn()
        # 防御性检查：确保工厂函数确实返回了 BaseTool
        if not isinstance(tool, BaseTool):
            import warnings
            warnings.warn(
                f"[tools_factory] {factory_fn.__name__} 未返回 BaseTool，已跳过。"
                f" 请确认 @tool 装饰器是否正确使用。"
            )
            continue
        generated.append(tool)

    # 按 tool.name 过滤
    if tool_names is not None:
        generated = get_tools_with_context_by_names(generated, tool_names)

    return _deduplicate_tools(generated)


def get_tools_with_context_by_names(tools: List[BaseTool], names: List[str]) -> List[BaseTool]:
    """
    从工具列表中按名字筛选。
    找不到指定名字的工具时会打印警告（不报错），方便开发调试。
    """
    name_set = set(names)
    found = []
    all_names = {t.name for t in tools}
    for t in tools:
        if t.name in name_set:
            found.append(t)
    missing = name_set - all_names
    if missing:
        import warnings
        warnings.warn(f"[filter_tools] 以下工具未找到: {missing}，可用工具有: {all_names}")
    return found
