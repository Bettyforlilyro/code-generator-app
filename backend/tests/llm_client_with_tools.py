# 测试 llm_client 是否能正常调用工具，直接执行即可
from backend.app.services.ai_common.chat_client_builder import ChatClientBuilder
from backend.app.services.ai_common.tools import get_all_tools_in_module, tools_factory_with_context


# ============================================================
# 辅助：打印工具列表
# ============================================================

def _print_tool_registry():
    """打印当前系统注册的所有工具，便于排查"""
    print("\n📦 系统已注册的无状态工具:")
    for t in get_all_tools_in_module():
        print(f"  - {t.name}: {t.description[:50]}...")

    ctx_tools = tools_factory_with_context()
    print(f"\n📦 系统已注册的带 context 工具 ({len(ctx_tools)} 个):")
    for t in ctx_tools:
        print(f"  - {t.name}: {t.description[:50]}...")


_print_tool_registry()

print("\n=== 调用工具测试 ===")
client1 = (
    ChatClientBuilder()
    .set_system_prompt("你是一个可以调用工具的AI助手")
    .add_tools_with_context_by_names(["计算器工具"])   # 注册带 context 的版本
    # .add_tools_by_names(["计算器工具"])              # 或者注册无状态版本
    .build()
)

# 触发工具调用 —— 传一个显然需要计算器的问题
response = client1.chat(
    messages=[{"role": "user", "content": "帮我算一下 6 + 10 * 3"}],
    tool_context={"user_id": "test_user", "request_id": "abc-123"},
)

print("\n=== 最终回复 ===")
print(response)


print("\n=== 流式调用工具测试 ===")
client2 = (
    ChatClientBuilder()
    .set_system_prompt("你是一个可以调用工具的AI助手")
    .add_tools_with_context_by_names(["计算器工具"])   # 注册带 context 的版本
    # .add_tools_by_names(["计算器工具"])              # 或者注册无状态版本
    .build()
)
messages = [
    {"role": "user", "content": "帮我算一下 15 + 27 * 3，然后用一句话告诉我结果"}
]

full_text = ""
chunks_received = 0
tool_start_markers = 0
tool_end_markers = 0
has_final_answer_96 = False

print("\n📡 开始接收流式数据:\n")

for chunk in client2.chat_stream(
        messages,
        conversation_id="test-stream-001",
        tool_context={"user_id": "test_user", "scene": "test_stream"},
):
    chunks_received += 1

    if chunk.is_last:
        print(f"\n🏁 [is_last=True] 总共收到 {chunks_received} 个 chunk")
        break

    # 实时打印（这就是用户看到的效果）
    print(chunk.content, end="", flush=True)
    full_text += chunk.content

    # 检查工具调用状态标记
    if "🛠️" in chunk.content:
        tool_start_markers += 1
        print("\n   ↑ [检测到工具调用开始标记]", flush=True)
    elif "✅" in chunk.content and "工具完成" in chunk.content:
        tool_end_markers += 1
        print("\n   ↑ [检测到工具调用结束标记]", flush=True)

print(f"\n\n📊 统计:")
print(f"  - 总 chunk 数: {chunks_received}")
print(f"  - 工具开始标记: {tool_start_markers}")
print(f"  - 工具结束标记: {tool_end_markers}")
print(f"  - 完整文本长度: {len(full_text)}")

print("\n=== 最终回复 ===")
print(full_text)

print("\n=== 流式调用工具测试（多轮调用） ===\n")
client3 = (
    ChatClientBuilder()
    .set_system_prompt("你是一个可以调用工具的AI助手，而且单轮只能调用一个工具")
    # .add_tools_with_context_by_names(["计算器工具", "文件写入工具"])   # 注册带 context 的版本
    .add_tools_by_names(["计算器工具", "文件写入工具"])              # 或者注册无状态版本
    .build()
)
messages = [
    {"role": "user", "content": "先帮我算一下 2024 除以 4，再把结果写到 year.txt 里"}
]

full_text = ""
chunks_received = 0
all_tool_names_seen = []

print("\n📡 开始接收流式数据:\n")

for chunk in client3.chat_stream(
    messages,
    conversation_id="test-stream-multi-001",
    tool_context={"user_id": "test_user", "scene": "test_stream"},
):
    chunks_received += 1
    if chunk.is_last:
        break

    print(chunk.content, end="", flush=True)
    full_text += chunk.content

    # 提取调用了哪些工具
    if "🛠️" in chunk.content and "调用工具" in chunk.content:
        # 简单提取工具名
        import re
        match = re.search(r'调用工具.*?`([^`]+)`', chunk.content)
        if match:
            all_tool_names_seen.append(match.group(1))

print(f"\n\n📊 调用了以下工具: {all_tool_names_seen}")
print(f"\n\n📊 统计:")
print(f"  - 总 chunk 数: {chunks_received}")
print(f"  - 完整文本长度: {len(full_text)}")
print(f"  - 工具调用次数: {len(all_tool_names_seen)}")
print(f"  - 完整回复：{full_text}")
