"""
工具执行核心模块

封装 LLM 工具调用的查找、执行、异常格式化、展示构建等纯函数逻辑，
从 ChatClient 中拆出，保持无状态、可独立测试。
"""
import traceback
from dataclasses import dataclass
from typing import List

from langchain_core.messages import ToolMessage

from backend.app.services.ai_common.tools import filter_tools_by_names, get_tool_display


@dataclass
class ToolExecResult:
    """单个 tool_call 的执行结果

    用独立字段区分「查找阶段」和「执行阶段」的结果，
    避免调用方依赖字符串前缀来分支（tuple 版的脆弱点）。
    """
    tool_name: str
    tool_call_id: str
    tool_args: dict
    # ---- 查找阶段 ----
    lookup_ok: bool = True
    lookup_error: str | None = None  # 查找失败时的原始错误信息
    # ---- 执行阶段（仅 lookup_ok=True 时有意义）----
    success: bool = False            # 执行是否无异常
    content: str = ""                # 工具返回值（或执行异常堆栈）


def execute_single_tool(
    tc: dict,
    available_tools: list,
) -> ToolExecResult:
    """
    执行单个 tool_call（查找 + invoke + 异常格式化）

    Args:
        tc: tool_calls 列表中的单条元素 {'name', 'args', 'id'}
        available_tools: ChatClient 已注册的工具实例列表

    Returns:
        ToolExecResult: 包含查找状态、执行状态、内容等完整信息
    """
    tool_name = tc['name']
    tool_call_id = tc.get('id', '')
    tool_args = tc.get('args', {})

    result = ToolExecResult(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        tool_args=tool_args,
    )

    # ---- 查找工具 ----
    try:
        matched = filter_tools_by_names(available_tools, [tool_name])
        if not matched:
            result.lookup_ok = False
            result.lookup_error = f"未注册的工具: {tool_name}"
            return result
        tool = matched[0]
    except Exception as e:
        result.lookup_ok = False
        result.lookup_error = str(e)
        return result

    # ---- 执行工具 ----
    try:
        raw = tool.invoke(tool_args)
        result.content = str(raw) if not isinstance(raw, str) else raw
        result.success = True
    except Exception as e:
        result.content = f"工具执行异常: {type(e).__name__}: {e}\n{traceback.format_exc()}"
        result.success = False

    return result


def execute_tool_calls_batch(
    tool_calls: list,
    available_tools: list,
) -> List[ToolMessage]:
    """
    同步批量执行 tool_calls，返回 ToolMessage 列表

    供 ChatClient._execute_tool_calls 复用。
    查找失败时 ToolMessage content 格式与原实现一致："工具查找失败: {e}"
    执行异常时 ToolMessage content 格式与原实现一致：包含 traceback 堆栈
    """
    tool_messages: List[ToolMessage] = []
    for tc in tool_calls:
        r = execute_single_tool(tc, available_tools)
        if not r.lookup_ok:
            tool_messages.append(
                ToolMessage(
                    content=f"工具查找失败: {r.lookup_error}",
                    tool_call_id=r.tool_call_id,
                )
            )
        else:
            tool_messages.append(
                ToolMessage(content=r.content, tool_call_id=r.tool_call_id)
            )
    return tool_messages


# ==================== 工具展示辅助 ====================

def build_tool_start_content(tool_name: str) -> str:
    """
    构建工具开始时的概览展示（只在 AI 规划阶段调用一次，此时参数还不完整）。
    完整参数和执行结果交给 build_tool_end_content 展示。
    优先使用 registry 注册的自定义 show_start（但签名变了：只传 tool_name），否则用默认格式。
    """
    display = get_tool_display(tool_name)
    custom_show = display.get("show_start")
    if callable(custom_show):
        try:
            return custom_show()  # 不再传 args，show_start 概览模式
        except Exception:
            pass
    return f"\n\n⚡ AI 准备调用: `{tool_name}` ...\n\n"


def build_tool_end_content(tool_name: str, args: dict, result: str, success: bool) -> str:
    """构建工具结束时给前端展示的 content：优先用 registry 注册的自定义展示，否则默认格式"""
    display = get_tool_display(tool_name)
    custom_show = display.get("show_end")
    if callable(custom_show):
        try:
            return custom_show(args, result, success)
        except Exception:
            pass
    icon = "✅" if success else "❌"
    status_text = "成功" if success else "失败"
    return f"{icon} **工具执行完成**: `{tool_name}` — {status_text}\n\n"  # 工具执行结果可能很长就不显示了