from typing import Optional, Any

from pydantic import BaseModel


class CreateAppResponse(BaseModel):
    """创建任务后的响应"""
    job_id: str
    app_id: str
    status_url: str


class JobStatusResponse(BaseModel):
    """任务状态查询响应"""
    job_id: str
    app_id: str
    status: str
    description: Optional[str] = None
    deploy_url: Optional[str] = None
    package_path: Optional[str] = None
    qa_report: Optional[str] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    detail: Optional[Any] = None