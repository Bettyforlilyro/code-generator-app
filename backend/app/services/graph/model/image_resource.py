"""
图片素材和资源模型
"""
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.app.services.graph.model.image_type_enum import ImageTypeEnum


class ImageResource(BaseModel):
    """
    图片素材和资源模型
    """
    category: ImageTypeEnum = Field(description="图片类别")
    description: Optional[str] = Field(description="图片描述")
    image_url: str = Field(description="图片URL")


def merge_image_list(old_list: List[ImageResource], new_list: List[ImageResource]) -> List[ImageResource]:
    """
    Reducer: 混合合并策略。
    - LOGO / ARCHITECTURE: 覆盖更新 (新图替换旧图)
    - CONTENT / ILLUSTRATION: 去重追加
    """
    if not new_list:
        return old_list or []
    if not old_list:
        return new_list

    # 定义需要覆盖的类型
    overwrite_types = {ImageTypeEnum.LOGO, ImageTypeEnum.ARCHITECTURE}

    # 1. 处理覆盖类型：找出新列表中属于覆盖类型的图片
    new_overwrite_images = [img for img in new_list if img.category in overwrite_types]
    new_overwrite_types = {img.category for img in new_overwrite_images}

    # 从旧列表中剔除被覆盖的类型
    merged_list = [img for img in old_list if img.category not in new_overwrite_types]

    # 2. 处理追加类型：找出新列表中属于追加类型的图片
    new_append_images = [img for img in new_list if img.category not in overwrite_types]

    # 提取当前已有 URL 用于去重
    existing_urls = {img.image_url for img in merged_list}

    # 追加去重
    for img in new_append_images:
        if img.image_url not in existing_urls:
            merged_list.append(img)
            existing_urls.add(img.image_url)

    # 最后把覆盖类型的新图片加进去
    merged_list.extend(new_overwrite_images)

    return merged_list
