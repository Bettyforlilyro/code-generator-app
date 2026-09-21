from enum import Enum


class ImageTypeEnum(str, Enum):
    CONTENT = "content"
    LOGO = "logo"
    ILLUSTRATION = "illustration"
    ARCHITECTURE = "architecture"

    @classmethod
    def get_all_image_types(cls) -> list:
        """获取所有图片类型"""
        return [cls.value for cls in ImageTypeEnum]

    @classmethod
    def get_response_format(cls) -> dict:
        """获取用于LLM的response_format配置"""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": cls.__name__,
                "schema": {
                    "description": "代码生成类型",
                    "type": "string",
                    "enum": cls.get_all_image_types(),
                },
                "strict": True
            }
        }

    @classmethod
    def is_valid_image_type(cls, image_type: str) -> bool:
        """检查图片类型是否有效"""
        return image_type in cls.get_all_image_types()
