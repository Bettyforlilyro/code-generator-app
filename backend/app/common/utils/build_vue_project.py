import logging
import os
import subprocess
import threading


def build_vue_project(project_path: str, timeout: int = 500) -> bool:
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
