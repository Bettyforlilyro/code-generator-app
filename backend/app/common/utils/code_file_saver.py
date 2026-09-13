"""
代码文件保存模块

职责：
    将 AI 生成的代码结果（HTML / 多文件等）落盘到服务器本地目录。
    采用策略模式 + 工厂模式设计：
    - CodeFileSaver（抽象类）：定义保存策略的统一接口
    - HTMLCodeFileSaver / MultiFileCodeFileSaver（具体策略）：实现单文件 / 多文件保存
    - CodeFileSaverFactory（工厂）：根据 CodeFileType 枚举选择合适的保存策略

落盘目录结构：
    {DEFAULT_GENERATE_ROOT}/html_{app_id}/index.html
    {DEFAULT_GENERATE_ROOT}/multi_file_{app_id}/index.html
                                /styles.css
                                /script.js
"""
import logging
import os
import subprocess
import threading
from abc import ABC, abstractmethod

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT
from backend.app.common.exceptions.error_codes import FileOperationError
from backend.app.schemas.ai_generate_results import BaseCodeResult, HtmlCodeResult, MultiFileCodeResult, \
    VueProjectFileCodeResult


class CodeFileSaver(ABC):
    """
    代码文件保存器抽象基类（策略模式）

    所有具体保存策略都需要继承此类并实现 save_code_file 方法。
    通过 CodeFileSaverFactory.get_saver() 可根据 CodeFileType 获取对应的实例。

    Attributes:
        path: 文件保存的根目录，默认值取自 constant.DEFAULT_GENERATE_ROOT
    """

    def __init__(self, path: str = "") -> None:
        """
        Args:
            path: 自定义文件保存根目录，为空则使用 DEFAULT_GENERATE_ROOT
        """
        self.path: str = path or DEFAULT_GENERATE_ROOT

    @abstractmethod
    def save_code_file(self, code_file: BaseCodeResult, app_id: int) -> str:
        """
        将代码结果保存到文件系统

        Args:
            code_file: AI 生成的代码结果 Pydantic 模型（HtmlCodeResult / MultiFileCodeResult 等）
            app_id: 关联的应用 ID，用于生成子目录名

        Returns:
            保存后的文件目录绝对路径

        Raises:
            TypeError: 传入的 code_file 类型与当前 Saver 不匹配
            FileOperationError: 文件写入失败（权限、磁盘等）
        """
        pass

    @staticmethod
    def _make_output_dir(root: str, sub_dir: str) -> str:
        """
        创建输出目录（若不存在则递归创建）

        Args:
            root: 根目录路径
            sub_dir: 子目录名（可为空字符串，表示直接使用 root）

        Returns:
            拼接后的完整目录路径
        """
        output_dir = os.path.join(root, sub_dir) if sub_dir else root
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    @staticmethod
    def _write_files(directory: str, files: dict[str, str]) -> None:
        """
        批量写入文件到指定目录，自动创建缺失的子目录

        Args:
            directory: 目标目录绝对路径
            files: 文件字典，key 为相对路径（如 "styles/main.css"），value 为文件内容

        Raises:
            FileOperationError: 文件写入失败
        """
        for filename, content in files.items():
            if not content:     # 跳过 None 值的文件或者空字符串
                continue
            filepath = os.path.join(directory, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            except (OSError, IOError) as e:
                raise FileOperationError(f"写入文件失败: {filepath}, 错误: {e}") from e


class HTMLCodeFileSaver(CodeFileSaver):
    """
    单 HTML 文件保存策略

    适用于 CodeFileType.HTML，将生成的 HtmlCodeResult 落盘为 {path}/html_{app_id}/index.html
    """

    def __init__(self, path: str = "") -> None:
        super().__init__(path)

    def save_code_file(self, code_result: HtmlCodeResult, app_id: int) -> str:
        """
        保存单个 HTML 文件

        Args:
            code_result: 必须为 HtmlCodeResult 类型
            app_id: 关联应用 ID

        Returns:
            HTML 文件所在目录的绝对路径

        Raises:
            TypeError: code_result 不是 HtmlCodeResult 类型
        """
        if not isinstance(code_result, HtmlCodeResult):
            raise TypeError(
                f"HTMLCodeFileSaver 只接受 HtmlCodeResult，收到 {type(code_result).__name__}"
            )

        output_dir = self._make_output_dir(self.path, f"html_{app_id}")
        self._write_files(output_dir, code_result.get_files_dict())
        return output_dir


class MultiFileCodeFileSaver(CodeFileSaver):
    """
    多文件保存策略（HTML + CSS + JS）

    适用于 CodeFileType.MULTI_FILE，将生成的 MultiFileCodeResult 落盘到
    {path}/multi_file_{app_id}/ 目录下
    """

    def __init__(self, path: str = "") -> None:
        super().__init__(path)

    def save_code_file(self, code_result: MultiFileCodeResult, app_id: int) -> str:
        """
        保存多文件代码（index.html, styles.css, script.js）

        Args:
            code_result: 必须为 MultiFileCodeResult 类型
            app_id: 关联应用 ID

        Returns:
            多文件所在目录的绝对路径

        Raises:
            TypeError: code_result 不是 MultiFileCodeResult 类型
        """
        if not isinstance(code_result, MultiFileCodeResult):
            raise TypeError(
                f"MultiFileCodeFileSaver 只接受 MultiFileCodeResult，收到 {type(code_result).__name__}"
            )

        output_dir = self._make_output_dir(self.path, f"multi_file_{app_id}")
        self._write_files(output_dir, code_result.get_files_dict())
        return output_dir


class VueProjectCodeFileSaver(CodeFileSaver):
    """
    Vue项目保存策略

    适用于 CodeFileType.VUE_PROJECT
    将生成的 VueProjectCodeResult 落盘到 {path}/vue_project_{app_id}/ 目录下
    然后执行 npm install 安装依赖和 npm run build 构建项目
    """
    def __init__(self, path: str = "") -> None:
        super().__init__(path)

    def save_code_file(self, code_result: VueProjectFileCodeResult, app_id: int) -> str:
        """
        并非保存 VUE 项目文件（文件已由 AI 工具直接落盘），
        而是进入项目目录安装依赖并执行构建，生成 dist 目录。
        耗时操作在子线程中执行，主线程等待结果，总超时 500s。

        Args:
            code_result: 必须为 VueProjectFileCodeResult 类型
            app_id: 关联应用 ID

        Returns:
            VUE 项目 dist 目录所在目录的相对路径（如 vue_project_{app_id}/dist），
            失败或超时时返回空字符串

        Raises:
            TypeError: code_result 不是 VueProjectFileCodeResult 类型
        """
        if not isinstance(code_result, VueProjectFileCodeResult):
            raise TypeError(
                f"VueProjectCodeFileSaver 只接受 VueProjectFileCodeResult，收到 {type(code_result).__name__}"
            )
        vue_project_path = os.path.join(DEFAULT_GENERATE_ROOT, f"vue_project_{app_id}")
        # 用 try catch 捕获异常，避免程序崩溃，内部消化异常并记录日志，不抛出异常
        try:
            if not self._build_vue_project(vue_project_path, timeout=500):
                return ""
            # 返回 dist 目录所在目录的相对路径
            return os.path.join(f"vue_project_{app_id}", "dist")
        except Exception as e:
            logging.error(f"Vue项目保存失败: {vue_project_path}, 错误: {e}")
            return ""

    @staticmethod
    def _build_vue_project(project_path: str, timeout: int = 500) -> bool:
        """
        在子线程中执行 npm install 和 npm run build，主线程等待结果。

        Args:
            project_path: Vue 项目根目录绝对路径
            timeout: 总超时时间（秒），子线程和子进程共用同一超时

        Returns:
            构建成功返回 True，超时或失败返回 False
        """
        if not os.path.isdir(project_path):
            logging.error(f"Vue项目目录不存在: {project_path}")
            return False

        result = {'success': False}
        # Windows 专用标志：防止弹出命令行黑窗
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        npm_ext = '.cmd' if os.name == 'nt' else ''
        # Windows 下 subprocess 默认为 GBK 编码，npm 输出含 UTF-8 字符，需要指定编码
        subproc_kwargs = dict(capture_output=True, text=True, encoding='utf-8', errors='replace')

        def _run_build():
            try:
                logging.info(f"开始执行 npm install, 目录: {project_path}")
                install_proc = subprocess.run(
                    [f'npm{npm_ext}', 'install'],
                    cwd=project_path,
                    timeout=timeout,
                    creationflags=creation_flags,
                    **subproc_kwargs,
                )
                if install_proc.returncode != 0:
                    logging.error(f"npm install 失败: {install_proc.stderr}")
                    return

                logging.info(f"开始执行 npm run build, 目录: {project_path}")
                build_proc = subprocess.run(
                    [f'npm{npm_ext}', 'run', 'build'],
                    cwd=project_path,
                    timeout=timeout,
                    creationflags=creation_flags,
                    **subproc_kwargs,
                )
                if build_proc.returncode != 0:
                    logging.error(f"npm run build 失败: {build_proc.stderr}")
                    return

                result['success'] = True
                logging.info(f"Vue项目构建成功: {project_path}")
            except subprocess.TimeoutExpired:
                import traceback
                logging.error(f"npm 命令执行超时（{timeout}s）: {project_path}, 错误: {traceback.format_exc()}")
            except Exception as e:
                import traceback
                logging.error(f"Vue项目构建异常: {e}, 错误: {traceback.format_exc()}")

        thread = threading.Thread(target=_run_build, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            logging.error(f"Vue项目构建总超时（{timeout}s）: {project_path}")
            return False

        return result['success']


class CodeFileSaverFactory:
    """
    代码文件保存器工厂（工厂模式）

    根据 CodeFileType 枚举返回对应的 CodeFileSaver 实现类实例。
    新增文件类型时，只需在 _saver_map 中注册即可，无需修改调用方。

    示例用法:
        saver = CodeFileSaverFactory.get_saver(CodeFileType.MULTI_FILE)
        directory = saver.save_code_file(result, app_id=123)
    """

    _saver_map: dict[CodeFileType, type[CodeFileSaver]] = {
        CodeFileType.HTML: HTMLCodeFileSaver,
        CodeFileType.MULTI_FILE: MultiFileCodeFileSaver,
        CodeFileType.VUE_PROJECT: VueProjectCodeFileSaver,
    }

    @classmethod
    def get_saver(cls, gen_type: CodeFileType) -> CodeFileSaver:
        """
        根据代码文件类型获取对应的保存器实例

        Args:
            gen_type: 代码生成文件类型枚举

        Returns:
            对应类型的 CodeFileSaver 实例

        Raises:
            ValueError: gen_type 未在 _saver_map 中注册
        """
        saver_cls = cls._saver_map.get(gen_type)
        if saver_cls is None:
            raise ValueError(f"未注册的代码文件生成类型: {gen_type}")
        return saver_cls()
