import logging
import os
import subprocess
import threading


def _do_build_vue_project(project_path: str, timeout: int) -> bool:
    """
    核心构建逻辑：同步阻塞执行 npm install + npm run build。

    Args:
        project_path: Vue 项目根目录绝对路径
        timeout: 单个命令超时时间（秒）

    Returns:
        构建成功返回 True，超时或失败返回 False
    """
    if not os.path.isdir(project_path):
        logging.error(f"Vue项目目录不存在: {project_path}")
        return False

    # Windows 专用标志：防止弹出命令行黑窗
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    npm_ext = '.cmd' if os.name == 'nt' else ''
    # Windows 下 subprocess 默认为 GBK 编码，npm 输出含 UTF-8 字符，需要指定编码
    subproc_kwargs = dict(capture_output=True, text=True, encoding='utf-8', errors='replace')

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
            return False

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
            return False

        logging.info(f"Vue项目构建成功: {project_path}")
        return True
    except subprocess.TimeoutExpired:
        logging.error(f"npm 命令执行超时（{timeout}s）: {project_path}")
        return False
    except Exception as e:
        logging.error(f"Vue项目构建异常: {e}")
        return False


def build_vue_project_async(project_path: str, timeout: int = 500) -> threading.Thread:
    """
    异步启动 Vue 项目构建，立即返回，不阻塞调用方。
    构建在后台守护线程中执行，不影响前端快速响应。

    Args:
        project_path: Vue 项目根目录绝对路径
        timeout: 单个命令超时时间（秒）

    Returns:
        后台构建线程（daemon=True，主线程退出时自动结束）
    """
    thread = threading.Thread(
        target=_do_build_vue_project,
        args=(project_path, timeout),
        daemon=True,
        name=f"vue-build-{os.path.basename(project_path)}",
    )
    thread.start()
    logging.info(f"Vue项目异步构建已启动: {project_path}")
    return thread


def build_vue_project_sync(project_path: str, timeout: int = 500) -> bool:
    """
    同步阻塞执行 Vue 项目构建，调用方会等待构建完成。

    Args:
        project_path: Vue 项目根目录绝对路径
        timeout: 单个命令超时时间（秒）

    Returns:
        构建成功返回 True，超时或失败返回 False
    """
    return _do_build_vue_project(project_path, timeout)