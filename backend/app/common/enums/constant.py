from backend.app.config import get_config

# 文件存储根目录（代码生成产物）
DEFAULT_GENERATE_ROOT = get_config().GENERATE_ROOT

# 部署目录
DEFAULT_DEPLOY_ROOT = get_config().DEFAULT_ROOT

# Nginx 可执行文件路径（仅 Windows 部署用到，Linux 用 apt 安装后通常在 /usr/sbin/nginx）
NGINX_PATH = get_config().NGINX_PATH
