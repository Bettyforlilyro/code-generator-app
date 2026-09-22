import logging
import mimetypes
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

IMAGE_BED_URL = os.getenv("IMAGE_BED_URL")
IMAGE_BED_TOKEN = os.getenv("IMAGE_BED_TOKEN")
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR")

# 图床支持的扩展名白名单
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}


def take_screenshot_and_save(
        url: str,
        output_path: str | None = None,
        img_type: str = "jpeg",
        quality: int | None = 80,
        width: int = 1280,
        height: int = 720,
        full_page: bool = False,
        timeout: int = 30000,
        extra_wait_ms: int = 0,
        disable_animations: bool = True,
        omit_background: bool = False,
) -> str:
    """
    截取网页截图并保存到指定路径

    Args:
        url: 目标网页 URL，必须带 scheme（如 https://）
        output_path: 截图保存目录，若为 None 则自动生成到 SCREENSHOT_DIR
        img_type: 图片格式，Playwright 仅支持 "png" | "jpeg"
        quality: 图片压缩质量 0-100，仅 jpeg 有效，png 忽略
        width: 视口宽度（CSS 像素）
        height: 视口高度（CSS 像素）
        full_page: 是否截取整个可滚动页面（而非仅可视区域）
        timeout: goto 和 screenshot 的超时时间，单位毫秒，0 表示禁用
        extra_wait_ms: goto 完成后的额外等待毫秒数（用于确保动态渲染完毕）
        disable_animations: 是否冻结 CSS 动画/过渡，避免截图时动画还在播放
        omit_background: 是否隐藏白色背景（仅 PNG 有效，支持透明截图）

    Returns:
        截图后保存的文件的绝对路径

    Raises:
        Exception: SSL 错误、URL 无效、超时、服务器不可达等
    """
    # 自动生成输出路径
    if output_path is None:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")[:50]
        output_path = f"{SCREENSHOT_DIR}/{safe_url}_{timestamp}.{img_type}"

    with sync_playwright() as p:
        # headless=True 为无头模式（不弹出浏览器）
        browser = p.chromium.launch(headless=True)

        # 设置 User-Agent 模拟真实浏览器
        context = browser.new_context(
            viewport={"width": width, "height": height},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            # 绕过一部分网站的反爬检测
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        page = context.new_page()

        try:
            # timeout 同时控制导航和截图
            page.set_default_timeout(timeout)

            page.goto(url, wait_until='load', timeout=timeout)

            # 额外等待（由调用方按需传入，默认 0）
            if extra_wait_ms:
                page.wait_for_timeout(extra_wait_ms)

            # 截图 —— type 仅支持 jpeg / png
            page.screenshot(
                path=output_path,
                full_page=full_page,
                type=img_type,
                quality=quality if img_type == "jpeg" else None,
                animations="disabled" if disable_animations else "allow",
                omit_background=omit_background if img_type == "png" else False,
            )

            logging.info(f"✅ 截图成功: {os.path.abspath(output_path)}")
            return os.path.abspath(output_path)

        except Exception as e:
            logging.error(f"❌ 截图失败: {e}")
            raise
        finally:
            browser.close()


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
