"""
代码质量审查节点（QA Agent）
对应流程图中「代码质量审查Agent」+「是否符合要求 || retry >= 3」判断框

职责：
1. 检查生成的代码是否有语法错误、引用问题等
2. 根据 code_gen_type 做针对性检查（HTML 禁止外部框架、Vue 必须 hash 路由等）
3. 返回 qa_pass / qa_feedback
4. 不通过且 retry_count < 3 时触发重试
"""
import json
import logging

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.schemas.ai_generate_results import VueProjectFileCodeResult, HtmlCodeResult, MultiFileCodeResult
from backend.app.services.ai_common.tools import tools_factory_with_context
from backend.app.services.graph.model.qa_ai_response import QAResult
from backend.app.services.graph.nodes.agent import create_spec_llm_in_graph
from backend.app.services.graph.prompt import QA_CHECK_SYSTEM_PROMPT
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

# 最大重试次数
MAX_RETRY = 3


def code_reviewer_node(state: WorkflowState) -> dict:
    """
    代码审查节点主函数
    如果是 vue 项目，需要通过目录读取工具、文件读取工具等相关工具读取文件内容再审查代码，generate_output 已经是 结构化的 VueProjectFileCodeResult
    如果是 html/multi_file 项目，直接从 generate_output 中提取 code_content 即可，generate_output 已经是 结构化的 HtmlCodeResult/MultiFileCodeResult

    Args:
        state: 当前工作流状态

    Returns:
        dict: 要更新到 state 中的字段
    """
    code_gen_type = state.get("code_gen_type", CodeFileType.HTML.value)
    is_vue_project = code_gen_type == CodeFileType.VUE_PROJECT.value
    generate_output = state.get("generate_output", "")
    # 从 generate_output 中提取需要的信息
    if isinstance(generate_output, VueProjectFileCodeResult):
        file_list = generate_output.vue_project_code_file_paths
        tech = "Vue 3框架开发"
        review_user_prompt = f"目前采用的技术栈：{tech}\n项目的所有代码保存在以下文件中：\n\n{file_list}，请检查这些代码是否符合要求。"
    elif isinstance(generate_output, HtmlCodeResult):
        code_content = generate_output.html_code
        tech = "单HTML"
        review_user_prompt = f"目前采用的技术栈：{tech}\n请检查以下 HTML 代码：\n\n{code_content}"
    elif isinstance(generate_output, MultiFileCodeResult):
        code_content = (f"HTML代码：\n{generate_output.html_code}\n\n"
                        f"CSS代码：\n{generate_output.css_code}\n\n"
                        f"JavaScript代码：\n{generate_output.js_code}")
        tech = "前端三件套（HTML/CSS/JavaScript）"
        review_user_prompt = f"目前采用的技术栈：{tech}\n请检查以下 HTML/CSS/JavaScript 代码：\n\n{code_content}"
    else:   # str 类型兜底，直接检查生成结果
        logger.warning(f"[code_reviewer] 未知的 code_gen_type: {code_gen_type}，或者解析 AI 回复格式错误")
        code_content = generate_output
        review_user_prompt = f"请检查下文中的代码：\n\n{code_content}"

    # 审查 system prompt 里要注入当前生成类型的特殊约束，如果是 vue 项目，需要注入目录读取、文件读取等相关工具
    llm_client = create_spec_llm_in_graph(
        system_prompt=QA_CHECK_SYSTEM_PROMPT,
        response_format=QAResult.get_response_format(),
        tools=tools_factory_with_context() if is_vue_project else [],
        timeout=300     # 审查代码时间可能较长
    )

    # 如果是重试，把之前的 feedback 也加入 prompt
    qa_feedback_history = state.get("qa_feedback", "")
    retry_count = state.get("retry_count", 0)
    if qa_feedback_history and retry_count > 0:
        review_user_prompt += (
            f"\n\n【上一轮审查反馈】（第 {retry_count} 次重试，请针对性修复）\n{qa_feedback_history}"
        )

    messages = [{"role": "user", "content": review_user_prompt}]

    try:
        tool_context = {
            "app_id": state.get("app_id"),
        } if is_vue_project else None
        qa_result = llm_client.chat_structured(messages, QAResult, tool_context=tool_context)
        logger.info(
            f"[code_reviewer] qa_pass={qa_result.qa_pass}, "
            f"feedback_length={len(qa_result.qa_feedback)}, retry={retry_count}"
        )
    except Exception as e:
        logger.error(f"[code_reviewer] 审查调用失败: {e}")
        qa_result = QAResult(
            qa_pass=False,
            qa_feedback=f"审查 Agent 调用异常: {e}",
        )

    new_retry_count = retry_count + 1 if not qa_result.qa_pass else retry_count

    return {
        "qa_pass": qa_result.qa_pass,
        "qa_feedback": qa_result.qa_feedback,
        "retry_count": new_retry_count,
        "current_node": "code_reviewer",
        # 审查通过情况下，将 code_generator 的结果保存到消息列表，由 reducer 自动合并
        # TODO 当前先将消息转换成 json 字符串临时保存观察效果
        "messages": json.dumps(generate_output),
    }


# ==================== 条件边函数 ====================

def route_after_code_reviewer(state: WorkflowState) -> str:
    """
    审查后的条件分支
    - qa_pass == True          → 保存构建
    - qa_pass == False 且 retry >= 3 → 保存构建（不再重试，让用户自己看）
    - qa_pass == False 且 retry < 3  → 回到 code_generator 重试
    """
    qa_pass = state.get("qa_pass", False)
    retry_count = state.get("retry_count", 0)

    if qa_pass or retry_count >= MAX_RETRY:
        return "save_or_build"
    else:
        logger.info(
            f"[code_reviewer] 审查未通过，第 {retry_count} 次重试，回到 code_generator"
        )
        return "code_generator"
