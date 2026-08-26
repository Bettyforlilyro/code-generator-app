from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel


class ResourceFileResponse(BaseModel):
    """单个静态资源文件响应"""
    file_name: str
    relative_path: str
    content: str
    size: int = 0


class ResourceFileNode(BaseModel):
    """静态资源节点响应（目录/文件，用于递归展示目录树）"""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    content: Optional[str] = None
    children: Optional[List['ResourceFileNode']] = None


# 前向引用的自引用类型，需要在定义后更新
ResourceFileNode.model_rebuild()


class ResourceFileListResponse(BaseModel):
    """静态资源目录列表响应"""
    deploy_id: str
    root_path: str
    files: List[ResourceFileNode]
    total_files: int = 0