from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.ai_common.tools import register_tool_display
from backend.app.services.ai_common.tools.tool_context_store import get_runtime_context


TOOL_NAME = "计算器工具"


class CalculateToolArgs(BaseModel):
    expression: str = Field(description="要计算的数学表达式，例如 '2 + 3 * 4'")


# ---------------------------------------------------------------------------
# 方式 A：无状态版本
# ---------------------------------------------------------------------------
@tool(
    description="计算数学表达式的值，例如加减乘除运算",
    args_schema=CalculateToolArgs
)
def calculate_tool(expression: str) -> str:
    try:
        result = eval(expression)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算失败: {type(e).__name__}: {e}"


calculate_tool.name = TOOL_NAME


# ---------------------------------------------------------------------------
# 方式 B：带 context 版本（工厂函数，无参，从 context_var 读取）
# ---------------------------------------------------------------------------
def calculate_tool_with_context():
    """
    工厂函数：返回计算器工具，每次执行时从 context_var 读取当前请求的 context。
    """

    @tool(
        description="计算数学表达式的值，例如加减乘除运算",
        args_schema=CalculateToolArgs
    )
    def _tool(expression: str) -> str:
        context = get_runtime_context()
        # 测试：打印一下 context 看是否正确透传
        print(f"[{TOOL_NAME}] context = {context}")

        try:
            result = eval(expression)
            return f"计算结果: {result}"
        except Exception as e:
            return f"计算失败: {type(e).__name__}: {e}"
    _tool.name = TOOL_NAME
    return _tool


def _show_start() -> str:
    return f"[{TOOL_NAME}] 开始计算"


def _show_end(args: dict, result: str, success: bool) -> str:
    return f"[{TOOL_NAME}] 计算结果: {result} ({success})"


register_tool_display(TOOL_NAME, _show_start, _show_end)
