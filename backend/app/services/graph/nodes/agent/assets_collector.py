"""
素材收集节点（图片素材 Agent）
对应流程图中「素材Agent」+ 四个图片工具

两阶段工作模式：
1. 规划阶段：chat_structured → ImageAIResponse（LLM 输出结构化收集计划）
2. 执行阶段：遍历 ImageAIResponse 里的每个任务项，手动调用对应的图片工具
3. 汇总阶段：把所有 ImageResource 写入 state.image_list（merge_image_list reducer 自动合并）

为什么用规划→执行，而不是 tool calling loop？
- 更可控：一次规划，不会出现 LLM 无限调工具或漏调的情况
- 工具直接返回 list[ImageResource]（Pydantic 对象），不需要 JSON 二次解析
- 规划模型强类型化（ImageAIResponse + 嵌套 SearchTask 等），chat_structured 解析更可靠
"""
import json
import logging
from typing import List

from backend.app.services.ai_common.llm_client import ChatClient
from backend.app.services.graph.model.image_ai_response import ImageAIResponse
from backend.app.services.graph.model.image_resource import ImageResource
from backend.app.services.graph.nodes.agent import create_spec_llm_in_graph
from backend.app.services.graph.nodes.tools.image_tools import (
    search_content_images,
    search_illustration_images,
    generate_architecture_image,
    generate_logo_image,
)
from backend.app.services.graph.prompt import MATERIAL_PLANNER_SYSTEM_PROMPT
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


# ============ 阶段 1：LLM 输出结构化规划 ============

def _plan_image_collection(
        enhanced_prompt: str,
        task_type: str,
        existing_images: List[ImageResource],
) -> ImageAIResponse:
    """
    让 LLM 根据网站需求输出图片收集计划（结构化 JSON → ImageAIResponse）

    关键点：这里只让 LLM 输出规划方案，**不绑定 tools**。
    tools 在阶段 2 手动调用。ChatClient.chat_structured 会自动解析 JSON 为 Pydantic 对象。

    Args:
        enhanced_prompt: 增强后的网站需求描述
        task_type: 任务类型（new_build / modify / chat）
        existing_images: modify 场景下已有的图片素材（告诉 LLM 可以复用哪些）

    Returns:
        ImageAIResponse 结构化规划结果
    """
    llm: ChatClient = create_spec_llm_in_graph(
        system_prompt=MATERIAL_PLANNER_SYSTEM_PROMPT,
        response_format=ImageAIResponse.get_response_format(),
        temperature=0.3,  # 规划不需要太高创造性
        # 注意：这里不传 tools，因为 chat_structured 模式下 tools 没用
    )

    messages: list = [{"role": "user", "content": enhanced_prompt}]

    if task_type == "modify" and existing_images:
        # 修改场景：告诉 LLM 已有素材，让它规划新增/替换部分
        existing_summary = json.dumps(
            [{"类别 category": img.category.value, "description": img.description}
             for img in existing_images],
            ensure_ascii=False,
        )
        messages.append({
            "role": "user",
            "content": (
                f"当前项目已有以下素材，如果没有特别说明需要替换，可以直接复用：\n"
                f"{existing_summary}\n\n"
                f"请根据用户的修改要求，仅规划需要新增或替换的素材。"
            ),
        })

    plan = llm.chat_structured(messages, ImageAIResponse)
    logger.info(
        f"[assets_collector] 规划完成: content={len(plan.content)}, "
        f"illustration={len(plan.illustration)}, architecture={len(plan.architecture)}, "
        f"logo={len(plan.logo)}"
    )
    return plan


# ============ 阶段 2：手动执行每个任务项 ============

def _execute_plan(plan: ImageAIResponse) -> List[ImageResource]:
    """
    根据 LLM 输出的规划，手动调用对应的图片工具

    Args:
        plan: ImageAIResponse 规划结果

    Returns:
        所有工具返回的 ImageResource 汇总（工具直接返回 list[ImageResource]，无需 JSON 解析）
    """
    collected: List[ImageResource] = []

    # TODO 后续可以优化成并行执行，可以考虑使用官方文档中的函数式API task

    # --- content 图片（Pexels 搜索）---
    for search_task in plan.content:
        try:
            results = search_content_images.invoke({"query": search_task.query, "count": search_task.count})
            collected.extend(results)
        except Exception as e:
            logger.error(f"    ← 失败: {e}")

    # --- illustration 插画（Undraw）---
    for search_task in plan.illustration:
        try:
            results = search_illustration_images.invoke({"query": search_task.query, "count": search_task.count})
            collected.extend(results)
        except Exception as e:
            logger.error(f"    ← 失败: {e}")

    # --- architecture 架构图（Mermaid CLI）---
    for architecture_task in plan.architecture:
        try:
            results = generate_architecture_image.invoke(
                {"mermaid_code": architecture_task.mermaid_code, "description": architecture_task.description}
            )
            collected.extend(results)
            logger.info(f"    ← 返回 {len(results)} 张 architecture 图片")
        except Exception as e:
            logger.error(f"    ← 失败: {e}")

    # --- logo 设计 --- 
    for logo_task in plan.logo:
        try:
            results = generate_logo_image.invoke({"description": logo_task.description})
            collected.extend(results)
            logger.info(f"    ← 返回 {len(results)} 张 logo 图片")
        except Exception as e:
            logger.error(f"    ← 失败: {e}")

    return collected


# ============ 节点主入口 ============

def assets_collector_node(state: WorkflowState) -> dict:
    """
    素材收集节点主函数

    Args:
        state: 当前工作流状态

    Returns:
        dict: 要更新到 state 中的字段
            - image_list: 新收集的图片（merge_image_list reducer 自动合并到已有列表）
            - current_node: 调试标记
    """
    enhanced_prompt = state.get("enhanced_prompt", "")
    task_type = state.get("task_type", "new_build")
    existing_images = state.get("image_list", [])

    # --- 阶段 1：LLM 规划 ---
    try:
        plan = _plan_image_collection(enhanced_prompt, task_type, existing_images)
    except Exception as e:
        logger.error(f"[assets_collector] 规划失败: {e}")
        return {"current_node": "assets_collector"}

    # --- 阶段 2：执行规划 ---
    try:
        collected_images = _execute_plan(plan)
        logger.info(f"[assets_collector] 总计收集到 {len(collected_images)} 张图片素材")
    except Exception as e:
        logger.error(f"[assets_collector] 执行规划失败: {e}")
        collected_images = []

    return {
        "image_list": collected_images,  # merge_image_list reducer 自动合并
        "current_node": "assets_collector",
    }
