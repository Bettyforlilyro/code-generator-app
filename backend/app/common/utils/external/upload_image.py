import mimetypes
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.app.config import get_config

IMAGE_BED_URL = get_config().IMAGE_BED_URL
IMAGE_BED_TOKEN = get_config().IMAGE_BED_TOKEN

# 图床支持的扩展名白名单
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}


def _detect_mime(file_path: str) -> str:
    """
    根据文件扩展名推断 MIME 类型。
    Python 标准库 mimetypes 对常见图片类型支持完整，SVG 也能正确返回 image/svg+xml。
    标准库覆盖不到时，回退到 application/octet-stream（PHP 后端仍有扩展名反推逻辑兜底）。
    """
    mime, _ = mimetypes.guess_type(file_path)
    return mime or "application/octet-stream"


def _build_session() -> requests.Session:
    """
    构建带自动重试的 Session：
    - 对 5xx 服务端错误和网络抖动最多重试 3 次
    - 只对幂等的 GET/HEAD/OPTIONS 自动重放（POST 不自动重放，避免重复上传）
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def upload_image_to_bed(image_path: str) -> str:
    """
    上传图片到图床，返回图片 URL
    暂时使用本地部署 easyimages 图床服务，后续可替换为其他图床服务，或者自行通过 COS 上传

    Args:
        image_path: 原图文件路径

    Returns:
        图片 URL

    Raises:
        Exception: 图片上传失败
    """
    path = Path(image_path)

    # 1) 前置校验：文件存在 + 扩展名合法（提前失败，避免无意义的网络请求）
    if not path.is_file():
        raise FileNotFoundError(f"图片不存在: {image_path}")

    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"不支持的图片格式 '{ext}'，允许: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2) 读取文件
    with path.open("rb") as f:
        image_data = f.read()

    # 3) 用 tuple 显式提供 filename + MIME
    mime_type = _detect_mime(image_path)
    files = {"image": (path.name, image_data, mime_type)}
    data = {"token": IMAGE_BED_TOKEN}

    # 4) 发送（带重试的 Session）
    session = _build_session()
    try:
        response = session.post(
            IMAGE_BED_URL,
            files=files,
            data=data,
            timeout=30,
        )
    except requests.RequestException as e:
        raise Exception(f"上传请求失败（网络/超时）: {e}") from e

    # 5) HTTP 层错误检查
    if response.status_code != 200:
        raise Exception(
            f"图片上传失败 HTTP {response.status_code}: {response.text[:200]}"
        )

    # 6) 业务层错误检查（重要！这个 API 失败时也返回 HTTP 200）
    try:
        result = response.json()
    except ValueError:
        raise Exception(f"上传响应不是合法 JSON: {response.text[:200]}")

    # API 返回格式: {"result":"success"/"failed", "code":0/400, "url":"...", "message":"..."}
    if result.get("result") != "success":
        raise Exception(
            f"图片上传失败(code={result.get('code')}): {result.get('message', '未知错误')}"
        )

    url = result.get("url")
    if not url:
        raise Exception(f"上传成功但缺少 url 字段: {result}")

    return url
