"""
AI生成结果的各种Pydantic模型定义
"""
import re
from abc import ABC, abstractmethod
from typing import Optional, List

from pydantic import BaseModel, Field


class BaseCodeResult(BaseModel, ABC):
    """基础代码生成结果模型"""
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
        return {"index.html": self.html_code if self.html_code else ""}

    def is_code_modified(self) -> bool:
        return self.html_code is not None and self.html_code.strip() != ""

    def is_name_modified(self) -> bool:
        return self.app_name is not None and self.app_name.strip() != ""

    @classmethod
    def parse_response_from_llm(cls, response: str) -> "HtmlCodeResult":
        """从LLM响应中解析代码生成结果"""
        result = cls()
        result.app_name = parse_app_name_from_response(response)
        # 解析HTML代码
        result.html_code = _extract_code_block(response, 'html')
        return result


class MultiFileCodeResult(BaseCodeResult):
    """多个文件代码生成结果"""
    html_code: Optional[str] = Field(description="生成的完整HTML代码", default=None)
    css_code: Optional[str] = Field(description="生成的完整CSS代码", default=None)
    js_code: Optional[str] = Field(description="生成的完整JavaScript代码", default=None)
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
            "index.html": self.html_code if self.html_code else "",
            "styles.css": self.css_code if self.css_code else "",
            "script.js": self.js_code if self.js_code else ""
        }

    def is_code_modified(self) -> bool:
        return self.html_code is not None or self.css_code is not None or self.js_code is not None

    def is_name_modified(self) -> bool:
        return self.app_name is not None and self.app_name.strip() != ""

    @classmethod
    def parse_response_from_llm(cls, response: str) -> "MultiFileCodeResult":
        """从LLM响应中解析代码生成结果"""
        result = cls()
        result.app_name = parse_app_name_from_response(response)
        # 从AI回复中提取可能存在的HTML/CSS/JavaScript代码
        result.html_code = _extract_code_block(response, 'html')
        result.css_code = _extract_code_block(response, 'css')
        result.js_code = _extract_code_block(response, 'javascript', 'js')
        return result


class VueProjectFileCodeResult(BaseCodeResult):
    """Vue项目文件代码生成结果"""
    vue_project_code_file_paths: Optional[List[str]] = Field(description="生成的完整Vue项目代码文件列表，包含多个文件路径", default=None)
    app_name: Optional[str] = Field(description="应用名称", default=None)

    def get_files_dict(self) -> dict[str, str]:
        return {file_path: "" for file_path in self.vue_project_code_file_paths}

    def is_code_modified(self) -> bool:
        return self.vue_project_code_file_paths is not None and len(self.vue_project_code_file_paths) > 0

    def is_name_modified(self) -> bool:
        return self.app_name is not None and self.app_name.strip() != ""

    @classmethod
    def parse_response_from_llm(cls, response: str) -> "VueProjectFileCodeResult":
        """从LLM响应中解析代码生成结果"""
        result = cls()
        # ✅ **写入完成** 文件写入成功，文件路径：package.json
        # 应用名称:<app_name>
        result.app_name = parse_app_name_from_response(response)
        write_success = re.compile(
            r'✅ \*\*写入完成\*\* 文件写入成功，文件路径：'           # 固定锚点
            r'([^\\\r\n/:*?"<>|]+(?:\\[^\\\r\n/:*?"<>|]+)*)'    # 分隔符为 \ 的相对路径
        )
        result.vue_project_code_file_paths = [match.group(1) for match in write_success.finditer(response)]
        return result


def parse_app_name_from_response(response: str) -> Optional[str]:
    pattern = re.compile(r'app_name:(.*)\n')
    if pattern.search(response):
        return pattern.search(response).group(1)
    return None


def _extract_code_block(response: str, *lang_names: str) -> Optional[str]:
    """从LLM响应中提取指定语言的代码块内容，支持多个语言别名，按顺序依次尝试匹配。

    使用 Markdown 规范 + 栈式嵌套配对，正确处理所有代码块场景：
    1. 缩进 >= 4 空格的 ``` 不算 fence（Markdown 规范）
    2. 每个 fence 必须是独立一行，反引号连续出现
    3. 有 info string 的 fence 是「开始」，无 info string 的 fence 是「闭合」
    4. 将目标起始 fence 也 push 进栈，栈归零时即为目标代码块真正闭合
    """
    # 匹配任意 fence 行：行首0-3空白 + 3+反引号 + info_string(不含反引号) + 可选空白
    fence_pattern = re.compile(r'^[ \t]{0,3}(`{3,})([^\n`]*?)(?:[ \t]*)', re.MULTILINE)

    for lang in lang_names:
        # 目标语言的起始 fence
        start_pattern = re.compile(rf'^[ \t]{{0,3}}`{{3,}}{re.escape(lang)}[ \t]*$', re.MULTILINE)
        start_match = start_pattern.search(response)
        if not start_match:
            continue

        # 提取目标起始 fence 的反引号长度并入栈
        raw_start = response[start_match.start():start_match.end()]
        target_fence_len = len(re.match(r'^[ \t]{0,3}(`{3,})', raw_start).group(1))
        stack = [target_fence_len]

        pos = start_match.end()
        close_match = None

        scan = fence_pattern.search(response, pos)
        while scan:
            info_string = scan.group(2).strip()

            if info_string == '':
                # 无 info string → 闭合栈顶
                if stack:
                    stack.pop()
                    if not stack:
                        close_match = scan
                        break
            else:
                # 有 info string → 新的嵌套代码块开始，进栈
                stack.append(len(scan.group(1)))

            scan = fence_pattern.search(response, scan.end())

        if close_match:
            content = response[pos:close_match.start()]
        else:
            # 没找到闭合，兜底取到文本末尾
            content = response[pos:]

        return content.strip()

    return None
