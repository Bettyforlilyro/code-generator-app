from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class AppCreateRequest(BaseModel):
    """应用创建请求模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "init_prompt": "创建一个现代化的个人博客网站",
                "app_name": "我的博客应用"
            }
        }
    )

    init_prompt: str = Field(
        ...,
        description="应用初始化的用户Prompt（必填）",
        examples=["创建一个现代化的个人博客网站"]
    )
    app_name: Optional[str] = Field(
        None,
        max_length=256,
        description="应用名称（可选，不传则使用init_prompt前20字符作为名称）",
        examples=["我的博客应用"]
    )
    app_coverage: Optional[str] = Field(
        None,
        max_length=1024,
        description="应用封面图标URL（可选）",
        examples=["https://example.com/coverage.jpg"]
    )


class AppUpdateRequest(BaseModel):
    """应用更新请求模型（用户自己修改）"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_name": "更新后的应用名称",
                "app_coverage": "https://example.com/new-coverage.jpg"
            }
        }
    )

    app_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=256,
        description="应用名称（可选）",
        examples=["更新后的应用名称"]
    )
    app_coverage: Optional[str] = Field(
        None,
        max_length=1024,
        description="应用封面图标URL（可选）",
        examples=["https://example.com/new-coverage.jpg"]
    )


class AdminAppUpdateRequest(BaseModel):
    """管理员应用更新请求模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_name": "管理员修改的应用名称",
                "app_coverage": "https://example.com/admin-coverage.jpg",
                "priority": 10
            }
        }
    )

    app_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=256,
        description="应用名称（可选）",
        examples=["管理员修改的应用名称"]
    )
    app_coverage: Optional[str] = Field(
        None,
        max_length=1024,
        description="应用封面图标URL（可选）",
        examples=["https://example.com/admin-coverage.jpg"]
    )
    priority: Optional[int] = Field(
        None,
        ge=0,
        description="首页展示优先级（可选，值越大越靠前）",
        examples=[10]
    )
