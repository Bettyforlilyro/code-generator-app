"""
LangGraph 工作流主入口

把所有节点组装成 StateGraph，对应项目流程图：

    START
      ↓
    task_evaluate ──(chat)────────────────────→ code_generator ──→ chat_history_save ──→ END
      │
      │ (new_build/modify)
      ↓
    assets_collector
      ↓
    type_router
      ↓
    code_generator
      │
      ↓ (new_build/modify)
    code_reviewer ──(qa_pass || retry>=3)──→ save_or_build ──→ chat_history_save ──→ END
      │
      │ (qa_pass=False && retry<3)
      ↓
    code_generator  (回到上一步重试)

对话历史保存规则（chat_history_save 节点）：
- chat 类型：总是保存 user + assistant
- new_build/modify：仅 qa_pass=True 或 retry>=3 时保存
- 审查未通过且 retry<3：跳过保存（还没最终结果）

使用方式：
    from backend.app.services.graph.workflow_graph import workflow_graph
    
    result = workflow_graph.invoke({
        "original_prompt": "帮我做一个博客网站",
        "app_id": 123,
        "user_id": 456,
        "messages": [...],
    })
"""
import logging

from langgraph.graph import StateGraph, START, END

from backend.app.services.graph.nodes.agent.assets_collector import assets_collector_node
from backend.app.services.graph.nodes.agent.code_generator import (
    code_generator_node,
    route_after_code_generator,
)
from backend.app.services.graph.nodes.agent.code_reviewer import (
    code_reviewer_node,
    route_after_code_reviewer,
)
from backend.app.services.graph.nodes.agent.task_evaluate import (
    task_evaluate_node,
    route_after_task_evaluate,
)
from backend.app.services.graph.nodes.agent.type_router import type_router_node
from backend.app.services.graph.nodes.save_or_build_project import save_or_build_project_node
from backend.app.services.graph.nodes.save_output_history import chat_history_save
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

# TODO 开发阶段，开启 INFO 日志打印，方便观察工作流执行流程
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


# ==================== 构建 Graph ====================

def _build_graph() -> StateGraph:
    """
    构建 StateGraph 并连接所有节点和条件边
    """
    graph = StateGraph(WorkflowState)

    # -------------------- 添加所有节点 --------------------
    graph.add_node("task_evaluate", task_evaluate_node)
    graph.add_node("assets_collector", assets_collector_node)
    graph.add_node("type_router", type_router_node)
    graph.add_node("code_generator", code_generator_node)
    graph.add_node("code_reviewer", code_reviewer_node)
    graph.add_node("save_or_build", save_or_build_project_node)
    graph.add_node("chat_history_save", chat_history_save)

    # -------------------- 边连接 --------------------

    # 1. START → task_evaluate
    graph.add_edge(START, "task_evaluate")

    # 2. task_evaluate 条件分支:
    #    - chat → 跳到 code_generator（直接回答问题）
    #    - new_build/modify → assets_collector（收集素材）
    graph.add_conditional_edges(
        "task_evaluate",
        route_after_task_evaluate,
        {
            "assets_collector": "assets_collector",
            "code_generator": "code_generator",
        },
    )

    # 3. assets_collector → type_router（素材收集完选生成模式）
    graph.add_edge("assets_collector", "type_router")

    # 4. type_router → code_generator（路由完开始生成代码）
    graph.add_edge("type_router", "code_generator")

    # 5. code_generator 条件分支:
    #    - chat 类型 → chat_history_save（先保存对话历史，再 END）
    #    - new_build/modify → code_reviewer（审查代码）
    graph.add_conditional_edges(
        "code_generator",
        route_after_code_generator,
        {
            "code_reviewer": "code_reviewer",
            "chat_history_save": "chat_history_save",
        },
    )

    # 6. code_reviewer 条件分支:
    #    - qa_pass=True 或 retry>=3 → save_or_build（审查通过或重试超限）
    #    - qa_pass=False 且 retry<3 → 回到 code_generator 重试
    graph.add_conditional_edges(
        "code_reviewer",
        route_after_code_reviewer,
        {
            "save_or_build": "save_or_build",
            "code_generator": "code_generator",
        },
    )

    # 7. save_or_build → chat_history_save（构建完成后保存对话历史）
    graph.add_edge("save_or_build", "chat_history_save")

    # 8. chat_history_save → END（对话历史保存完，流程结束）
    graph.add_edge("chat_history_save", END)

    return graph


# ==================== 编译 & 导出 ====================

# 编译后的可执行 Graph（单例，整个应用共享）
workflow_graph = _build_graph().compile()


def get_workflow_graph():
    """
    获取编译后的工作流 Graph
    
    Returns:
        Compiled StateGraph 实例
    """
    return workflow_graph


def run_workflow(
        original_prompt: str,
        app_id: int | None = None,
        user_id: int | None = None,
        messages: list | None = None,
) -> dict:
    """
    便捷执行入口（非流式）：快速跑一轮工作流，用于测试和调试
    
    Args:
        original_prompt: 用户原始输入
        app_id: 应用 ID（文件保存、对话历史持久化需要）
        user_id: 用户 ID（对话历史持久化需要）
        messages: 历史对话消息（ChatMemoryManager 会覆盖 DB 加载的历史）

    Returns:
        最终的 state dict
    """
    initial_state: dict = _build_initial_state(original_prompt, app_id, user_id, messages)

    logger.info(f"[workflow_graph] 开始执行 (invoke), prompt={original_prompt[:50]!r}, app_id={app_id}")
    final_state = workflow_graph.invoke(initial_state)
    logger.info(
        f"[workflow_graph] 执行完成, task_type={final_state.get('task_type')}, "
        f"code_gen_type={final_state.get('code_gen_type')}, "
        f"qa_pass={final_state.get('qa_pass')}, "
        f"retry_count={final_state.get('retry_count')}"
    )
    return final_state


def _build_initial_state(
    original_prompt: str,
    app_id: int | None = None,
    user_id: int | None = None,
    messages: list | None = None,
) -> dict:
    """构建初始 state（invoke 和 stream 共用）"""
    initial_state = {
        "original_prompt": original_prompt,
        "messages": messages or [],
        "retry_count": 0,
        "qa_pass": False,
        "qa_feedback": None,
    }
    if app_id:
        initial_state["app_id"] = app_id
    if user_id:
        initial_state["user_id"] = user_id
    return initial_state


def run_workflow_streaming(
        original_prompt: str,
        app_id: int | None = None,
        user_id: int | None = None,
        messages: list | None = None,
):
    """
    流式执行入口 —— 核心方法

    使用 LangGraph 官方推荐的双模式流式：
    stream_mode=["updates", "custom"]

    ┌──────────────────────────────────────────────────────────────────┐
    │ custom 模式 ← 节点内部 get_stream_writer() 吐的事件              │
    │                                                                  │
    │ code_generator_node 内部：                                       │
    │   for chunk in chat_stream():                                    │
    │     event_type, data = processed_chunk(chunk)  ← 节点内就转好   │
    │     writer({"event_type": event_type, "data": data})             │
    │                                                                  │
    │ 外层直接 yield 这个格式 → 和 generate_code_and_save_file_streaming│
    │ 完全一致                                                         │
    ├──────────────────────────────────────────────────────────────────┤
    │ updates 模式 ← 节点 return dict 后 LangGraph 合并 state          │
    │   用于条件边判断（route_after_code_generator 等）和调试日志       │
    └──────────────────────────────────────────────────────────────────┘

    yield 格式 (三元组):
        ("stream", event_type, data)  —— 流式 chunk（给前端的实时输出）
        ("state", node_name, updates) —— 普通节点状态更新（调试用）
    """
    initial_state = _build_initial_state(original_prompt, app_id, user_id, messages)

    logger.info(f"[workflow_graph] 开始流式执行, prompt={original_prompt[:50]!r}, app_id={app_id}")

    # 双模式 stream：custom 拿节点 writer 推的实时事件，updates 拿节点完成后的 state 合并
    for mode, payload in workflow_graph.stream(
            initial_state, stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            # ✅ 节点内部 writer() 吐出来的事件 —— 已经是前端约定格式
            # payload = {"event_type": "message", "data": {"d": "..."}}
            event_type = payload.get("event_type", "message")
            data = payload.get("data", {})
            # 过滤掉空的 message chunk（chunk.content 为空时）
            if event_type == "message" and not data.get("d"):
                continue
            logger.info(f"[custom stream] type={event_type}, content={str(data)[:60]}")
            yield "stream", event_type, data

        elif mode == "updates":
            # LangGraph updates 模式返回的是 dict: {node_name: updates}
            for node_name, updates in payload.items():
                if not updates:
                    continue
                preview_fields = {}
                for key in ["current_node", "task_type", "code_gen_type",
                            "qa_pass", "retry_count", "generate_output"]:
                    if key in updates:
                        val = updates[key]
                        if isinstance(val, str) and len(val) > 60:
                            val = val[:60] + "..."
                        elif hasattr(val, '__class__') and val.__class__.__module__.startswith('pydantic'):
                            val = f"{val.__class__.__name__}(...)"
                        preview_fields[key] = val
                logger.info(f"[updates] node={node_name}, updates={preview_fields}")
                yield "state", node_name, updates

    logger.info("[workflow_graph] 流式执行完成")


# ==================== 可视化调试 & 流式测试 ====================

if __name__ == "__main__":
    # 打印 Mermaid 图
    mermaid_code = workflow_graph.get_graph().draw_mermaid(with_styles=False)
    print("mermaid_code:\n", mermaid_code)
    print("\n" + "=" * 50 + "\n")

    # ===== 测试 1：流式 chat 类型（最简单，能看到逐 token 效果）=====
    # print("【流式测试 1】chat 类型 — 直接回答问题")
    # print("-" * 50)
    # for kind, *payload in run_workflow_streaming(
    #     original_prompt="什么是 SPA 和 SSR 的区别？用简洁的语言解释",
    #     app_id=999,
    #     user_id=1001,
    # ):
    #     if kind == "stream":
    #         event_type, data = payload
    #         if event_type == "message":
    #             print(f"  [message] {data.get('d', '')}", end="", flush=True)
    #         else:
    #             print(f"  [{event_type}] {data}")
    #     else:
    #         node_name, updates = payload
    #         print(f"  → [{node_name}] state keys={list(updates.keys())}")
    # print("\n")

    # ===== 测试 2：流式 new_build（能看到 code_generator 多次 yield + tool 调用）=====
    print("【流式测试 2】new_build 类型 — 生成简单 VUE 单页应用")
    print("-" * 50)
    for kind, *payload in run_workflow_streaming(
        original_prompt="创建一个基于Vue3的单页应用，包含登录、注册、个人中心、文章列表、详情页、分类标签、搜索功能、评论系统和个人简介页面。采用简洁的设计风格，支持响应式布局，文章支持Markdown格式，首页展示最新文章和热门推荐。总代码控制在500行以内，不要写太多示例数据和演示文本",
        app_id=998,
        user_id=1001,
    ):
        if kind == "stream":
            event_type, data = payload
            if event_type == "message":
                print(f"  [message] {data.get('d', '')}", end="", flush=True)
            elif event_type == "task_start":
                print(f"\n  🔧 tool_start: {data.get('info', '')}")
            elif event_type == "task_end":
                print(f"  ✅ tool_end: {data.get('info', '')}")
            else:
                print(f"  [{event_type}] {data}")
        else:
            node_name, updates = payload
            preview = {}
            for k in ["task_type", "code_gen_type", "qa_pass", "retry_count", "current_node"]:
                if k in updates:
                    v = updates[k]
                    if isinstance(v, str) and len(v) > 50:
                        v = v[:50] + "..."
                    preview[k] = v
            print(f"  → [{node_name}] {preview}")

    print()
