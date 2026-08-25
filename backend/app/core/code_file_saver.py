import os
from abc import ABC, abstractmethod
from datetime import datetime

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.models.ai_generate_results import BaseCodeResult, HtmlCodeResult, MultiFileCodeResult


class CodeFileSaver(ABC):

    DEFAULT_ROOT = r"D:\projects\code-generator-app\backend\tests"

    def __init__(self, path: str = ""):
        self.path = path or self.DEFAULT_ROOT

    """代码文件保存器"""
    @abstractmethod
    def save_code_file(self, code_file: BaseCodeResult, app_id: int) -> str:
        """保存代码文件，返回保存路径（保存的目录）"""
        pass

    @staticmethod
    def _make_output_dir(root: str, sub_dir: str) -> str:
        """创建输出目录"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_dir = os.path.join(root, sub_dir, timestamp) if sub_dir else os.path.join(root, timestamp)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    @staticmethod
    def _write_files(directory: str, files: dict[str, str]) -> None:
        """批量写入文件，自动创建缺失的子目录"""
        for filename, content in files.items():
            filepath = os.path.join(directory, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)


class HTMLCodeFileSaver(CodeFileSaver):
    """单 HTML 文件保存器"""

    def __init__(self, path: str = ""):
        super().__init__(path)

    def save_code_file(self, code_result: HtmlCodeResult, app_id: int) -> str:
        if not isinstance(code_result, HtmlCodeResult):
            raise TypeError(f"HTMLCodeFileSaver 只接受 HtmlCodeResult，收到 {type(code_result).__name__}")

        output_dir = self._make_output_dir(self.path, f"html_{app_id}")
        self._write_files(output_dir, code_result.get_files_dict())
        return output_dir


class MultiFileCodeFileSaver(CodeFileSaver):
    """多文件保存器（HTML + CSS + JS）"""

    def __init__(self, path: str = ""):
        super().__init__(path)

    def save_code_file(self, code_result: MultiFileCodeResult, app_id: int) -> str:
        if not isinstance(code_result, MultiFileCodeResult):
            raise TypeError(f"MultiFileCodeFileSaver 只接受 MultiFileCodeResult，收到 {type(code_result).__name__}")

        output_dir = self._make_output_dir(self.path, f"multi_file_{app_id}")
        self._write_files(output_dir, code_result.get_files_dict())
        return output_dir
# ========== 可以扩展其他文件类型保存器 ==========


class CodeFileSaverFactory:
    """代码文件保存器工厂类"""
    _saver_map: dict[CodeFileType, type[CodeFileSaver]] = {
        CodeFileType.HTML: HTMLCodeFileSaver,
        CodeFileType.MULTI_FILE: MultiFileCodeFileSaver,
    }

    @classmethod
    def get_saver(cls, gen_type: CodeFileType) -> CodeFileSaver:
        saver_cls = cls._saver_map.get(gen_type)
        if saver_cls is None:
            raise ValueError(f"未注册的生成文件类型: {gen_type}")
        return saver_cls()
