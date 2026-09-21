import operator
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from typing_extensions import TypedDict, Annotated

load_dotenv()


def mock_llm(state: MessagesState):
    return {"messages": [{"role": "assistant", "content": "Hello, world!"}]}


graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)
graph = graph.compile()
result = graph.invoke({"messages": [{"role": "user", "content": "你好"}]})
print(result)
print("-----------------\n\n")


# 定义工具和模型
@tool()
def multiply(a: int, b: int) -> int:
    """将两个整数相乘"""
    return a * b


@tool(
    name_or_callable="add",
    description="将两个整数相加，返回结果"
)
def add(a: int, b: int) -> int:
    """将两个整数相加"""
    return a + b


@tool()
def subtract(a: int, b: int) -> int:
    """将两个整数相减"""
    return a - b


tools = [multiply, add, subtract]
tools_by_name = {tool.name: tool for tool in tools}
llm_params = {
    'api_key': os.getenv("TONGYI_API_KEY"),
    'base_url': os.getenv("TONGYI_OPENAI_COMPATIBLE_BASE_URL"),
    'model': os.getenv("TONGYI_MODEL")
}
model = ChatOpenAI(**llm_params)
response = model.invoke("你好")
model_with_tools = model.bind_tools(tools)


# 定义状态
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


# 定义模型 node
def llm_node(state: dict):
    """
    LLM decides whether to use tools or to continue the conversation.
    """
    return {
        "messages": [
            model_with_tools.invoke(
                [SystemMessage(
                    content="你是一个智能助手，你可以使用工具来回答用户的问题。"
                )]
                + state["messages"]
            )
        ]
    }


# 定义工具 node
def tool_node(state: dict):
    """
    Tools are called here.
    """
    ret = []
    for tool_call in state["messages"][-1].tool_calls:
        tool_name = tool_call.get("name")
        args = tool_call.get("args")
        observation = tools_by_name[tool_name].invoke(args)
        ret.append(ToolMessage(
            content=observation,
            tool_call_id=tool_call.get("id")
        ))
    return {"messages": ret}


# 定义条件边（结束逻辑）
def should_continue(state: MessagesState) -> Literal['tool_node', END]:
    """
    判断是否继续调用模型
    """
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


# 构建 graph 智能体并编译
graph = StateGraph(MessagesState)

graph.add_node("llm_node", llm_node)
graph.add_node("tool_node", tool_node)

graph.add_edge(START, "llm_node")
graph.add_conditional_edges(
    "llm_node",
    should_continue,
    ["tool_node", END]
)
graph.add_edge("tool_node", "llm_node")
graph = graph.compile()


# 显示 graph 图表
print(graph.get_graph().draw_mermaid(with_styles=False), end="\n\n", flush=True)
print("-----------------\n\n", flush=True)

# 执行 graph 智能体
messages = [HumanMessage(content="你好，12 + (3 * 6) = ?")]
stream = graph.stream_events({"messages": messages}, version='v3')
for message in stream.messages:
    for token in message.text:
        print(token, end="\n", flush=True)
final_state = stream.output
print("final_state:", final_state)

# stream = graph.stream(
#     {"messages": messages},
#     stream_mode=["updates", "messages", "values"],  # 订阅这三个通道的输出，分别代表 node 增量、message全量、全局状态
#     version='v2'
# )
# for chunk in stream:
#     if chunk["type"] == "messages":
#         print("messages: ", chunk["data"][0].content)
#     elif chunk["type"] == "values":
#         print("current state: ", chunk["data"])
#     elif chunk["type"] == "updates":
#         print("updates: ", chunk["data"])
