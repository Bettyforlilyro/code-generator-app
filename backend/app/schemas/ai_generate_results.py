"""
AI生成结果的各种Pydantic模型定义
"""
import re
from abc import ABC, abstractmethod
from typing import Optional, List

from pydantic import BaseModel, Field


class BaseCodeResult(BaseModel, ABC):
    """基础代码生成结果模型"""
    description: str = Field(description="简要说明")
    app_name: Optional[str] = Field(description="应用名称", default=None)

    @abstractmethod
    def get_files_dict(self) -> dict[str, str]:
        """获取代码文件字典 {"file_name": "file_content"} """
        pass

    @abstractmethod
    def is_code_modified(self) -> bool:
        """判断代码是否修改"""
        pass

    @abstractmethod
    def is_name_modified(self) -> bool:
        """判断应用名称是否修改"""
        pass

    @classmethod
    @abstractmethod
    def parse_response_from_llm(cls, response: str) -> "BaseCodeResult":
        """从LLM响应中解析代码生成结果"""
        pass


class HtmlCodeResult(BaseCodeResult):
    """单个HTML文件代码生成结果"""
    html_code: Optional[str] = Field(description="生成的完整HTML代码", default=None)
    description: str = Field(description="简要说明")
    app_name: Optional[str] = Field(description="应用名称", default=None)

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

    def is_code_modified(self) -> bool:
        return self.html_code is not None

    def is_name_modified(self) -> bool:
        return self.app_name is not None

    @classmethod
    def parse_response_from_llm(cls, response: str) -> "HtmlCodeResult":
        """从LLM响应中解析代码生成结果"""
        return cls.model_validate_json(response)


class MultiFileCodeResult(BaseCodeResult):
    """多个文件代码生成结果"""
    html_code: Optional[str] = Field(description="生成的完整HTML代码", default=None)
    css_code: Optional[str] = Field(description="可选的完整CSS代码", default=None)
    js_code: Optional[str] = Field(description="可选的完整JavaScript代码", default=None)
    description: str = Field(description="简要说明")
    app_name: Optional[str] = Field(description="应用名称", default=None)

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

    def is_code_modified(self) -> bool:
        return self.html_code is not None or self.css_code is not None or self.js_code is not None

    def is_name_modified(self) -> bool:
        return self.app_name is not None

    @classmethod
    def parse_response_from_llm(cls, response: str) -> "MultiFileCodeResult":
        """从LLM响应中解析代码生成结果"""
        return cls.model_validate_json(response)


class VueProjectFileCodeResult(BaseCodeResult):
    """Vue项目文件代码生成结果"""
    vue_project_code_file_paths: Optional[List[str]] = Field(description="生成的完整Vue项目代码文件列表，包含多个文件路径", default=None)
    description: str = Field(description="简要说明")
    app_name: Optional[str] = Field(description="应用名称", default=None)

    def get_files_dict(self) -> dict[str, str]:
        return {file_path: "" for file_path in self.vue_project_code_file_paths}

    def is_code_modified(self) -> bool:
        return self.vue_project_code_file_paths is not None and len(self.vue_project_code_file_paths) > 0

    def is_name_modified(self) -> bool:
        return self.app_name is not None

    @classmethod
    def parse_response_from_llm(cls, response: str) -> "VueProjectFileCodeResult":
        """从LLM响应中解析代码生成结果"""
        # TODO 这里的项目比较复杂，解析逻辑需要根据实际情况调整
        result = cls(description=response)
        # ✅ **写入完成** 文件写入成功，文件路径：package.json
        # 应用名称:<app_name>
        write_success = re.compile(
            r'✅ \*\*写入完成\*\* 文件写入成功，文件路径：'           # 固定锚点
            r'([^\\\r\n/:*?"<>|]+(?:\\[^\\\r\n/:*?"<>|]+)*)'    # 分隔符为 \ 的相对路径
        )
        app_name_pattern = re.compile(r'应用名称:(.*)\n')
        result.vue_project_code_file_paths = [match.group(1) for match in write_success.finditer(response)]
        if app_name_pattern.search(response):
            result.app_name = app_name_pattern.search(response).group(1)
        return result


