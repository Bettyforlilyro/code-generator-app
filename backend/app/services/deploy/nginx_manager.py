import logging
import os
import subprocess
from typing import Optional

from backend.app.common.enums import NGINX_PATH

logger = logging.getLogger(__name__)


class NginxManager:
    """Nginx 进程管理器（跨平台）"""

    def __init__(self, nginx_path: Optional[str] = None):
        self._nginx_path = nginx_path or NGINX_PATH

    def is_running(self) -> bool:
        """检查 nginx 进程是否正在运行"""
        try:
            if os.name == 'nt':
                return self._check_windows()
            else:
                return self._check_linux()
        except Exception as e:
            logger.error(f"检查 nginx 进程失败: {str(e)}")
            return False

    def start(self) -> bool:
        """启动 nginx"""
        try:
            if os.name == 'nt':
                return self._start_windows()
            else:
                return self._start_linux()
        except Exception as e:
            logger.error(f"启动 nginx 失败: {str(e)}")
            return False

    def _check_windows(self) -> bool:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq nginx.exe'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return 'nginx.exe' in result.stdout.lower()

    def _check_linux(self) -> bool:
        try:
            result = subprocess.run(
                ['pgrep', '-x', 'nginx'],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except FileNotFoundError:
            result = subprocess.run(
                ['sh', '-c', 'ps aux | grep nginx | grep -v grep'],
                capture_output=True,
                text=True,
            )
            return bool(result.stdout.strip())

    def _start_windows(self) -> bool:
        subprocess.Popen(
            [self._nginx_path],
            cwd=os.path.dirname(self._nginx_path),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True

    def _start_linux(self) -> bool:
        cmd = self._nginx_path if (self._nginx_path and os.path.isfile(self._nginx_path)) else 'nginx'
        subprocess.Popen([cmd])
        return True


# 单例工厂（大部分场景不需要多次实例化）
_default_manager: Optional[NginxManager] = None


def get_default_nginx_manager() -> NginxManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = NginxManager()
    return _default_manager
