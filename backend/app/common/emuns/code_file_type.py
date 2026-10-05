from enum import Enum


class CodeFileType(str, Enum):
    """代码文件类型枚举"""
    HTML = "html"
    MULTI_FILE = "multi_file"
    VUE_PROJECT = "vue_project"

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
                    "enum": [cls.HTML.value, cls.MULTI_FILE.value, cls.VUE_PROJECT.value],
                },
                "strict": True
            }
        }

    @classmethod
    def get_all_file_types(cls):
        """获取所有文件类型列表"""
        return [cls.HTML.value, cls.MULTI_FILE.value, cls.VUE_PROJECT.value]

    @classmethod
    def is_valid_file_type(cls, file_type: str) -> bool:
        """验证文件类型是否有效"""
        return file_type in cls.get_all_file_types()

    def __str__(self):
        return self.value

    @classmethod
    def model_validate_json(cls, json_str: str) -> "CodeFileType":
        """不能继承 pydantic 模型的 model_validate_json 方法，需要自定义。从JSON字符串中解析CodeFileType"""
        if not json_str:
            raise ValueError("JSON字符串不能为空")
        if cls.HTML.value in json_str:
            return cls.HTML
        elif cls.MULTI_FILE.value in json_str:
            return cls.MULTI_FILE
        elif cls.VUE_PROJECT.value in json_str:
            return cls.VUE_PROJECT
        else:
            raise ValueError(f"JSON字符串中未包含有效文件类型: {json_str}")
