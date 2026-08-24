from enum import Enum

from backend.app.models.ai_generate_results import HtmlCodeResult, MultiFileCodeResult
from backend.app.services.ai_common.prompts import *


class CodeFileType(str, Enum):
    """代码文件类型枚举"""
    HTML = "html"
    MULTI_FILE = "multi_file"

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
        }
        return cls_map.get(file_type, None)

    @classmethod
    def get_system_prompt(cls, file_type):
        """获取枚举类的系统提示词"""
        system_prompt_map = {
            cls.HTML.value: CODE_GENERATE_HTML_SYSTEM_PROMPT,
            cls.MULTI_FILE.value: CODE_GENERATE_MULTI_FILE_SYSTEM_PROMPT,
        }
        return system_prompt_map.get(file_type, None)

    def __str__(self):
        return self.value

