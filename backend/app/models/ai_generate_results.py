"""
AI生成结果的各种Pydantic模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional
from abc import ABC, abstractmethod


class BaseCodeResult(BaseModel, ABC):
    """基础代码生成结果模型"""
    description: str = Field(description="简要说明")
    app_name: str = Field(description="应用名称")

    @abstractmethod
    def get_files_dict(self) -> dict[str, str]:
        """获取代码文件字典 {"file_name": "file_content"} """
        pass


class HtmlCodeResult(BaseCodeResult):
    """单个HTML文件代码生成结果"""
    html_code: str = Field(description="生成的完整HTML代码")
    description: str = Field(description="简要说明")
    app_name: str = Field(description="应用名称")

    @classmethod
    def get_response_format(cls) -> dict:
        """获取用于LLM的response_format配置"""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": cls.__name__,
                "schema": cls.model_json_schema(),
                "strict": True
            }
        }

    def get_files_dict(self) -> dict[str, str]:
        return {"index.html": self.html_code}


class MultiFileCodeResult(BaseCodeResult):
    """多个文件代码生成结果"""
    html_code: str = Field(description="生成的完整HTML代码")
    css_code: Optional[str] = Field(description="可选的完整CSS代码", default=None)
    js_code: Optional[str] = Field(description="可选的完整JavaScript代码", default=None)
    description: str = Field(description="简要说明")
    app_name: str = Field(description="应用名称")

    @classmethod
    def get_response_format(cls) -> dict:
        """获取用于LLM的response_format配置"""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": cls.__name__,
                "schema": cls.model_json_schema(),
                "strict": True
            }
        }

    def get_files_dict(self) -> dict[str, str]:
        return {
            "index.html": self.html_code,
            "styles.css": self.css_code if self.css_code else "",
            "script.js": self.js_code if self.js_code else ""
        }
