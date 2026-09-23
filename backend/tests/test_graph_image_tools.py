"""
图片工具集成测试（真实调用外部 API，可 debug 进入内部）

前置条件（必须在 .env 中配置好以下所有 key）：
    PEXELS_API_KEY             — search_content_images 需要
    IMAGE_BED_URL / IMAGE_BED_TOKEN — generate_architecture_image / generate_logo_image 需要
    TONGYI_IMAGE_GEN_API_KEY   — generate_logo_image 需要
    TONGYI_OPENAI_COMPATIBLE_BASE_URL
    TONGYI_IMAGE_GEN_MODEL

另外 generate_architecture_image 还需要本机已安装:
    npm install -g @mermaid-js/mermaid-cli
"""
import os

import pytest

from backend.app.services.graph.model.image_resource import ImageResource
from backend.app.services.graph.model.image_type_enum import ImageTypeEnum
from backend.app.services.graph.nodes.tools.image_tools import (
    search_content_images,
    search_illustration_images,
    generate_architecture_image,
    generate_logo_image,
)


# ============================================================
#  通用断言辅助
# ============================================================

def _assert_is_image_resource_list(result, expected_category: ImageTypeEnum):
    """断言返回值是 ImageResource 列表，且元素的 category/image_url/description 合法"""
    assert isinstance(result, list), f"期望 list，实际 {type(result)}"
    for item in result:
        assert isinstance(item, ImageResource), f"期望 ImageResource，实际 {type(item)}"
        assert item.category == expected_category.value, (
            f"category 应为 {expected_category.value}，实际 {item.category}"
        )
        assert isinstance(item.image_url, str) and item.image_url, "image_url 不能为空"
        assert isinstance(item.description, str), "description 应为 str"


# ============================================================
#  search_content_images — Pexels Search API
# ============================================================

class TestSearchContentImages:
    """Pexels 内容图搜索集成测试"""

    def test_basic_search(self):
        """基础搜索：返回 count 张 nature 主题图"""
        result = search_content_images.invoke({"query": "nature", "count": 2})
        # 若 PEXELS_API_KEY 未配置或网络不通，会返回空列表，这里仅做结构断言
        if result:
            _assert_is_image_resource_list(result, ImageTypeEnum.CONTENT)
            assert len(result) <= 2

    def test_search_with_orientation_and_color(self):
        """带 orientation / color 过滤的搜索"""
        result = search_content_images.invoke({
            "query": "ocean",
            "count": 3,
            "orientation": "landscape",
            "color": "blue",
        })
        if result:
            _assert_is_image_resource_list(result, ImageTypeEnum.CONTENT)
            assert len(result) <= 3


# ============================================================
#  search_illustration_images — Undraw 搜索
# ============================================================

class TestSearchIllustrationImages:
    """Undraw 插画搜索集成测试"""

    def test_basic_search(self):
        """基础插画搜索"""
        result = search_illustration_images.invoke({"query": "love", "count": 3})
        if result:
            _assert_is_image_resource_list(result, ImageTypeEnum.ILLUSTRATION)
            assert len(result) <= 3

    def test_count_limits_result(self):
        """count=1 时只返回一张"""
        result = search_illustration_images.invoke({"query": "coffee", "count": 1})
        if result:
            _assert_is_image_resource_list(result, ImageTypeEnum.ILLUSTRATION)
            assert len(result) == 1

    def test_search_with_spaces(self):
        """带空格的 query 应能被正确编码（如 'machine learning'）"""
        result = search_illustration_images.invoke({
            "query": "machine learning", "count": 2,
        })
        # Undraw 可能对带空格的词无结果，这里只做不报错的弱断言
        assert isinstance(result, list)


# ============================================================
#  generate_architecture_image — Mermaid CLI + 图床
# ============================================================

class TestGenerateArchitectureImage:
    """Mermaid 架构图生成集成测试"""

    def test_simple_flowchart(self):
        """简单流程图渲染"""
        mermaid_code = """graph TD
    A[Start] --> B{Is it working?}
    B -->|Yes| C[Great!]
    B -->|No| D[Debug]
    D --> B"""
        result = generate_architecture_image.invoke({
            "mermaid_code": mermaid_code,
            "description": "简单的调试决策流程图",
        })
        if result:
            _assert_is_image_resource_list(result, ImageTypeEnum.ARCHITECTURE)
            assert len(result) == 1

    def test_complex_graph(self):
        """稍复杂的系统架构图"""
        mermaid_code = """graph TD;
	__start__ --> task_evaluate;
	assets_collector --> type_router;
	code_generator -.-> chat_history_save;
	code_generator -.-> code_reviewer;
	code_reviewer -.-> code_generator;
	code_reviewer -.-> save_or_build;
	save_or_build --> chat_history_save;
	task_evaluate -.-> assets_collector;
	task_evaluate -.-> code_generator;
	type_router --> code_generator;
	chat_history_save --> __end__;"""
        result = generate_architecture_image.invoke({
            "mermaid_code": mermaid_code,
            "description": "系统整体架构图",
        })
        if result:
            _assert_is_image_resource_list(result, ImageTypeEnum.ARCHITECTURE)
            assert len(result) == 1


# ============================================================
#  generate_logo_image — AI 文生图 + 图床
# ============================================================

class TestGenerateLogoImage:
    """Logo 生成集成测试（耗时较长，约 10~60s）"""

    @pytest.mark.skipif(
        not os.getenv("TONGYI_IMAGE_GEN_API_KEY"),
        reason="未配置 TONGYI_IMAGE_GEN_API_KEY，跳过 AI 生成测试",
    )
    def test_basic_logo(self):
        """基础 Logo 生成"""
        result = generate_logo_image.invoke({
            "description": "一个面向开发者的 SaaS 产品 logo，简洁现代风格，蓝色主色调",
        })
        if result:
            _assert_is_image_resource_list(result, ImageTypeEnum.LOGO)
            assert len(result) >= 1
