from enum import Enum

from backend.app.schemas.ai_generate_results import HtmlCodeResult, MultiFileCodeResult, VueProjectFileCodeResult
from backend.app.services.ai_common.prompts import *


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
        return [file_type.value for file_type in cls]

    @classmethod
    def is_valid_file_type(cls, file_type: str) -> bool:
        """验证文件类型是否有效"""
        return file_type in cls.get_all_file_types()

    @classmethod
    def get_cls_type(cls, file_type):
        """获取枚举类的文件结果类型"""
        cls_map = {
            cls.HTML.value: HtmlCodeResult,
            cls.MULTI_FILE.value: MultiFileCodeResult,
            cls.VUE_PROJECT.value: VueProjectFileCodeResult,
        }
        return cls_map.get(file_type, None)

    @classmethod
    def get_system_prompt(cls, file_type):
        """获取枚举类的系统提示词"""
        system_prompt_map = {
            cls.HTML.value: CODE_GENERATE_HTML_SYSTEM_PROMPT,
            cls.MULTI_FILE.value: CODE_GENERATE_MULTI_FILE_SYSTEM_PROMPT,
            cls.VUE_PROJECT.value: CODE_GENERATE_VUE_PROJECT_SYSTEM_PROMPT,
        }
        return system_prompt_map.get(file_type, None)

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
