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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from backend.app.services.ai_common import ChatClient
from backend.app.services.graph.model import ImageResource, ImageAIResponse
from backend.app.services.graph.nodes.tools import (
    search_content_images,
    search_illustration_images,
    generate_architecture_image,
    generate_logo_image,
)
from backend.app.services.graph.state.workflow_state import WorkflowState
from backend.app.services.prompts import IMAGE_COLLECTION_PLAN_SYSTEM_PROMPT
from . import create_spec_llm_in_graph

logger = logging.getLogger(__name__)


# ============ 阶段 1：LLM 输出结构化规划 ============

def _plan_image_collection(
        enhanced_prompt: str,
        app_id: str,
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
        system_prompt=IMAGE_COLLECTION_PLAN_SYSTEM_PROMPT,
        app_id=app_id,
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
    根据 LLM 输出的规划，并行调用所有图片工具（ThreadPoolExecutor）

    4 类图片工具完全独立（content / illustration / architecture / logo），
    同类工具内的多个任务也互不依赖，全部并发执行最大化网络 IO 利用率。

    Args:
        plan: ImageAIResponse 规划结果

    Returns:
        所有工具返回的 ImageResource 汇总（工具直接返回 list[ImageResource]，无需 JSON 解析）
    """
    collected: List[ImageResource] = []

    # ---- 先把所有工具调用提交成 futures ----
    futures = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        # --- content 图片（Pexels 搜索）---
        for task in plan.content:
            futures.append(executor.submit(
                search_content_images.invoke,
                {"query": task.query, "count": task.count}
            ))

        # --- illustration 插画（Undraw）---
        for task in plan.illustration:
            futures.append(executor.submit(
                search_illustration_images.invoke,
                {"query": task.query, "count": task.count}
            ))

        # --- architecture 架构图（Mermaid CLI）---
        for task in plan.architecture:
            futures.append(executor.submit(
                generate_architecture_image.invoke,
                {"mermaid_code": task.mermaid_code, "description": task.description}
            ))

        # --- logo 设计 ---
        for task in plan.logo:
            futures.append(executor.submit(
                generate_logo_image.invoke,
                {"description": task.description}
            ))

        # ---- 收集所有结果（按完成顺序）----
        for future in as_completed(futures):
            try:
                results = future.result()
                collected.extend(results)
            except Exception as e:
                logger.error(f"[assets_collector] 工具调用异常: {e}")

    logger.info(f"[assets_collector] 执行完成，共收集 {len(collected)} 张图片")
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
        app_id = state.get("app_id", "")
        plan = _plan_image_collection(enhanced_prompt, app_id, task_type, existing_images)
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
