import os

# 文件存储根目录（代码生成产物）
DEFAULT_GENERATE_ROOT = os.getenv(
    "GENERATE_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..", "..", "generated_apps"),
)

# 部署目录
DEFAULT_DEPLOY_ROOT = os.getenv(
    "DEPLOY_ROOT",
    os.path.join(DEFAULT_GENERATE_ROOT, "deployed"),
)

# Nginx 可执行文件路径（仅 Windows 部署用到，Linux 用 apt 安装后通常在 /usr/sbin/nginx）
NGINX_PATH = os.getenv("NGINX_PATH", r"D:\Nginx\nginx.exe")
