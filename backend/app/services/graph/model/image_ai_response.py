"""
素材收集规划 — LLM 结构化输出模型

对应 MATERIAL_PLANNER_SYSTEM_PROMPT 中要求的 JSON 格式：
```json
{
    "content": [{"query": "搜索关键词", "count": 2}],
    "illustration": [{"query": "插画关键词", "count": 1}],
    "architecture": [{"mermaid_code": "graph TD...", "description": "用途说明"}],
    "logo": [{"description": "Logo设计描述：名称、行业、风格等"}]
}
```

assets_collector 节点会先通过 chat_structured 拿到这个模型，
再遍历里面的每个任务项，手动调用对应的图片工具。
"""
from typing import List

from pydantic import BaseModel, Field


class SearchTask(BaseModel):
    """搜索类任务（内容图片 / 插画图片共用）"""
    query: str = Field(description="搜索关键词")
    count: int = Field(default=2, description="需要的图片数量")


class ArchitectureTask(BaseModel):
    """架构图任务"""
    mermaid_code: str = Field(description="Mermaid 图表代码")
    description: str = Field(description="用途说明")


class LogoTask(BaseModel):
    """Logo 设计任务"""
    description: str = Field(description="Logo 设计描述：名称、行业、风格、颜色偏好等")


class ImageAIResponse(BaseModel):
    """图片素材收集规划总览"""
    content: List[SearchTask] = Field(default_factory=list, description="内容图片搜索任务列表")
    illustration: List[SearchTask] = Field(default_factory=list, description="插画图片搜索任务列表")
    architecture: List[ArchitectureTask] = Field(default_factory=list, description="架构图任务列表")
    logo: List[LogoTask] = Field(default_factory=list, description="Logo 设计任务列表")

    @classmethod
    def get_response_format(cls) -> dict:
        """JSON 响应格式"""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": cls.__name__,
                "schema": cls.model_json_schema(),
                "strict": True
            }
        }
