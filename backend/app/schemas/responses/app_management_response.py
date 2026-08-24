from typing import Optional, List
from pydantic import BaseModel, Field


class AppCreateResponse(BaseModel):
    """应用创建响应"""
    id: int
    app_name: str
    init_prompt: str
    user_id: int


class AppDetailResponse(BaseModel):
    """应用详情响应"""
    id: int
    app_name: str
    app_coverage: Optional[str] = None
    init_prompt: Optional[str] = None
    code_gen_type: Optional[str] = None
    deploy_key: Optional[str] = None
    deploy_time: Optional[str] = None
    priority: int = 0
    user_id: int
    edit_time: Optional[str] = None
    create_time: Optional[str] = None
    update_time: Optional[str] = None


class AppSummaryResponse(BaseModel):
    """应用简要信息响应（列表展示用）"""
    id: int
    app_name: str
    app_coverage: Optional[str] = None
    code_gen_type: Optional[str] = None
    deploy_key: Optional[str] = None
    deploy_time: Optional[str] = None
    priority: int = 0
    user_id: int
    create_time: Optional[str] = None
    update_time: Optional[str] = None


class AppListResponse(BaseModel):
    """应用列表响应"""
    apps: List[AppSummaryResponse]
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool
