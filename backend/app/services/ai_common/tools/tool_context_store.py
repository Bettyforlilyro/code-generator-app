import contextvars
from typing import Dict, Any

# 创建请求级别的上下文变量（每个 asyncio task / thread 独立）
_context_var: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "tool_runtime_context", default={}
)


def set_runtime_context(context: Dict[str, Any]) -> None:
    """每次 chat() 调用前设置当前请求的运行时上下文"""
    _context_var.set(context)


def get_runtime_context() -> Dict[str, Any]:
    """工具内部用来获取当前请求的最新上下文"""
    return _context_var.get()


def reset_runtime_context() -> None:
    """请求结束后清理（可选，ContextVar 会自动随请求销毁）"""
    _context_var.set({})
