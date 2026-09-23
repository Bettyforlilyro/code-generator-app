"""
图片资源相关工具（LangChain tools）

提供四类图片获取能力：
1. search_content_images       - Pexels 网页搜索内容图片
2. search_illustration_images  - Undraw 插画抓取
3. generate_architecture_image - 架构图（Mermaid 转图片）
4. generate_logo_image         - Logo 设计图（AI 生成）

注意：当前为 Mock 实现，返回占位图片 URL。后续可替换为真实 API 调用。
"""
import logging
import os
import shutil
import subprocess
import tempfile
from http import HTTPStatus
from typing import List
from urllib.parse import quote

import dashscope
import requests
from dashscope import MultiModalConversation
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.common.utils.save_webpage_screenshot import upload_image_to_bed
from backend.app.services.graph.model.image_resource import ImageResource
from backend.app.services.graph.model.image_type_enum import ImageTypeEnum

logger = logging.getLogger(__name__)

load_dotenv()

# ============ Pexels API 配置 ============
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PEXELS_DEFAULT_TIMEOUT = 10

# Pexels API 支持的枚举参数值（用于校验）
_VALID_ORIENTATIONS = {"landscape", "portrait", "square"}
_VALID_SIZES = {"large", "medium", "small"}

# ============ Undraw API 配置 ============
# Next.js build id，Undraw 站点发布新版本后需更新
UNDRAW_BUILD_ID = "9SMsYpCjXCftNdh3cu_8Q"
UNDRAW_SEARCH_URL_TEMPLATE = (
    "https://undraw.co/_next/data/{build_id}/search/{query}.json?term={query}"
)
UNDRAW_DEFAULT_TIMEOUT = 10


# ============ Pexels API 辅助函数 ============

def _call_pexels_search(
    query: str,
    per_page: int = 15,
    page: int = 1,
    orientation: str | None = None,
    size: str | None = None,
    color: str | None = None,
    locale: str | None = None,
) -> dict | None:
    """
    调用 Pexels Search API

    Args:
        query: 搜索关键词（必填）
        per_page: 每页数量，1~80
        page: 页码，默认 1
        orientation: 可选，landscape / portrait / square
        size: 可选，large / medium / small
        color: 可选，命名颜色 (red 等) 或十六进制 (#ff0000)
        locale: 可选，搜索语言 (en-US / zh-CN 等)

    Returns:
        解析后的 JSON dict；请求失败或 API Key 未配置时返回 None
    """
    if not PEXELS_API_KEY:
        logger.warning("[pexels] PEXELS_API_KEY 未配置，跳过真实调用")
        return None

    params: dict = {"query": query, "per_page": per_page, "page": page}
    if orientation and orientation in _VALID_ORIENTATIONS:
        params["orientation"] = orientation
    if size and size in _VALID_SIZES:
        params["size"] = size
    if color:
        params["color"] = color
    if locale:
        params["locale"] = locale

    try:
        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers={"Authorization": PEXELS_API_KEY},
            params=params,
            timeout=PEXELS_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"[pexels] 搜索请求失败: {e}")
        return None


def _extract_image_url(photo: dict, prefer: str = "large2x") -> str:
    """
    从 Pexels 返回的 photo 对象中提取最佳图片 URL

    优先顺序: prefer(默认 large2x) -> large -> original -> medium -> small

    Args:
        photo: Pexels API 返回的单张 photo dict
        prefer: 首选尺寸 key，对应 src 子字段

    Returns:
        图片 URL；无可用值时返回空字符串
    """
    src = photo.get("src", {}) or {}
    priority = (prefer, "large", "original", "medium", "small")
    for key in priority:
        url = src.get(key)
        if url:
            return url
    return ""


def _call_undraw_search(query: str) -> list[dict]:
    """
    调用 Undraw 插画搜索 API（Next.js 内部接口）

    Args:
        query: 搜索关键词

    Returns:
        Undraw initialResults 列表；请求/解析失败时返回空列表
    """
    encoded = quote(query, safe="")
    url = UNDRAW_SEARCH_URL_TEMPLATE.format(
        build_id=UNDRAW_BUILD_ID, query=encoded
    )
    try:
        resp = requests.get(url, timeout=UNDRAW_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("pageProps", {}).get("initialResults", [])
        return results if isinstance(results, list) else []
    except requests.RequestException as e:
        logger.error(f"[undraw] 搜索请求失败: {e}")
        return []
    except (ValueError, KeyError) as e:
        logger.error(f"[undraw] 响应解析失败: {e}")
        return []


def _mermaid_to_image(mermaid_code: str) -> str | None:
    """
    本地调用 Mermaid CLI (mmdc) 将 mermaid 代码渲染为 SVG，
    再上传图床返回公开 URL。

    流程：写临时 .mermaid → mmdc 渲染 → 上传图床 → 清理临时文件

    Args:
        mermaid_code: 完整的 Mermaid 图表源码

    Returns:
        图床 URL；任何环节失败均返回 None
    """
    # 1. 定位 mmdc 可执行文件（Windows 需要 mmdc.cmd）
    mmdc_name = "mmdc.cmd" if os.name == 'nt' else "mmdc"
    mmdc_path = shutil.which(mmdc_name)
    if not mmdc_path:
        logger.error(
            f"[mermaid] 未找到 {mmdc_name}，请先安装: npm install -g @mermaid-js/mermaid-cli"
        )
        return None

    # 2. 在临时目录中写入源码并渲染
    tmp_dir = tempfile.mkdtemp(prefix="mermaid_")
    try:
        input_path = os.path.join(tmp_dir, f"diagram.mermaid")
        output_path = os.path.join(tmp_dir, f"diagram.svg")

        with open(input_path, "w", encoding="utf-8") as f:
            f.write(mermaid_code)

        cmd = [
            mmdc_path,
            "-i", input_path,
            "-o", output_path,
            "-b", "transparent",
        ]
        logger.info(f"[mermaid] 执行: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.error(f"[mermaid] mmdc 渲染失败: {result.stderr.strip()}")
            return None

        if not os.path.isfile(output_path):
            logger.error("[mermaid] mmdc 执行成功但未生成输出文件")
            return None

        # 3. 上传图床
        url = upload_image_to_bed(output_path)
        logger.info(f"[mermaid] 图床上传成功: {url}")
        return url

    except subprocess.TimeoutExpired:
        logger.error("[mermaid] mmdc 渲染超时 (>30s)")
        return None
    except Exception as e:
        logger.error(f"[mermaid] 渲染/上传异常: {e}")
        return None
    finally:
        # 4. 无论成功失败都清理临时目录
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============ 工具定义 ============

class ImageSearchArgs(BaseModel):
    query: str = Field(description="搜索的关键词")
    count: int = Field(description="需要的图片数量，默认是2", default=2)


@tool(
    description="根据关键词搜索内容相关的图片（产品图、场景图、人物图等），用于网站内容展示。",
    args_schema=ImageSearchArgs
)
def search_content_images(
    query: str,
    count: int = 2,
    orientation: str | None = None,
    color: str | None = None,
) -> list[ImageResource]:
    """
    根据关键词搜索内容图片（产品图、场景图、人物图等）。
    接入 Pexels Search API。
    未配置 PEXELS_API_KEY 或请求失败时，自动降级返回 Mock 占位图。

    Args:
        query: 搜索关键词（建议用英文，效果更好）
        count: 需要的图片数量，默认 2，最大 80
        orientation: 可选，图片方向：landscape / portrait / square
        color: 可选，期望颜色：red / blue / #ff5500 等

    Returns:
        图片资源列表
    """
    per_page = min(max(count, 1), 80)
    logger.info(
        f"[tool] search_content_images: query={query}, count={count}, "
        f"orientation={orientation}, color={color}"
    )

    data = _call_pexels_search(
        query=query,
        per_page=per_page,
        orientation=orientation,
        color=color,
    )

    result = []
    # 降级：API 调用失败或无结果时回退到 Mock 数据
    if data is None or not data.get("photos"):
        logger.warning(f"[tool] search_content_images 未搜索到相关图片资源，请重试或更换搜索关键词！")
    for photo in data["photos"][:count]:
        image_url = _extract_image_url(photo)
        if not image_url:
            continue
        result.append(
            ImageResource(
                category=ImageTypeEnum.CONTENT.value,
                description=photo.get("alt") or query,
                image_url=image_url,
            )
        )
    return result


@tool(
    description="根据关键词搜索装饰性插画图片，来自 Undraw 免费插画库，用于网站装饰或视觉点缀。",
    args_schema=ImageSearchArgs
)
def search_illustration_images(
    query: str, count: int = 2
) -> list[ImageResource]:
    """
    根据关键词搜索装饰性插画图片（来自 Undraw 插画库）。
    Undraw 不支持服务端分页和 count，一次返回全量结果，函数内部按 count 截取。

    Args:
        query: 插画风格/主题关键词
        count: 需要的插画数量，默认 2

    Returns:
        图片资源列表
    """
    logger.info(f"[tool] search_illustration_images: query={query}, count={count}")

    results = _call_undraw_search(query)

    if not results:
        logger.warning(
            f"[tool] search_illustration_images 未搜索到相关插画，请重试或更换关键词！"
        )
        return []

    result: list[ImageResource] = []
    for item in results[:count]:
        media_url = item.get("media") or ""
        if not media_url:
            continue
        result.append(
            ImageResource(
                category=ImageTypeEnum.ILLUSTRATION.value,
                description=item.get("title") or query,
                image_url=media_url,
            )
        )
    return result


class MermaidArgs(BaseModel):
    mermaid_code: str = Field(description="Mermaid 图表代码")
    description: str = Field(description="架构图说明")


@tool(
    description="将 Mermaid 代码转换为架构图/流程图图片，用于展示系统结构和技术关系。",
    args_schema=MermaidArgs
)
def generate_architecture_image(
    mermaid_code: str, description: str
) -> list[ImageResource]:
    """
    根据 Mermaid 代码生成架构图/流程图。

    Args:
        mermaid_code: Mermaid 图表代码（graph TD / flowchart LR 等）
        description: 图表用途说明

    Returns:
        图片资源列表
    """
    logger.info(f"[tool] generate_architecture_image: desc={description}")

    image_url = _mermaid_to_image(mermaid_code)
    if not image_url:
        logger.warning(
            f"[tool] generate_architecture_image 渲染失败，请检查 mermaid 代码或 mmdc程序/图床服务是否正常！"
        )
        return []

    return [
        ImageResource(
            category=ImageTypeEnum.ARCHITECTURE.value,
            description=description,
            image_url=image_url,
        )
    ]


class LogoArgs(BaseModel):
    description: str = Field(description="Logo 设计描述，如名称、行业、风格、颜色偏好等，尽量详细")


@tool(
    description="根据描述生成 Logo 设计图片，用于网站品牌标识。",
    args_schema=LogoArgs
)
def generate_logo_image(description: str) -> list[ImageResource]:
    """
    根据描述生成 Logo 设计图片，使用文生图大模型API，收费偏贵，慎用。

    Args:
        description: Logo 设计描述，如名称、行业、风格、颜色偏好等，尽量详细

    Returns:
        图片资源列表
    """
    # TODO 代码已写好，但是测试由于成本过高，开发阶段统一返回 mock 数据，开发完成后删除这段 return
    return [
        ImageResource(
            category=ImageTypeEnum.LOGO.value,
            description=description,
            image_url="http://easyimages:90/app/thumb.php?img=/i/2026/09/22/zjsch2-0.png",
        )
    ]

    logger.info(f"[tool] generate_logo_image: desc={description}")
    logo_prompt = f"生成一张 Logo 图片，Logo中禁止包含任何文字！Logo 介绍：{description}"
    dashscope.base_http_api_url = os.getenv("TONGYI_DASHSCOPE_BASE_URL")
    temp_dir = tempfile.mkdtemp(prefix="logo_")
    messages = [{
        "role": "user",
        "content": [{
                "text": logo_prompt
        }]
    }]
    try:
        rsp = MultiModalConversation.call(
            api_key=os.getenv("TONGYI_IMAGE_GEN_API_KEY"),
            model=os.getenv("TONGYI_IMAGE_GEN_MODEL"),
            messages=messages,
            result_format='message',
            stream=False,
            watermark=False,
            prompt_extend=True,
            negative_prompt="水印、签名、照片写实、3D 渲染、复杂背景、渐变背景、杂乱、多个 logo、样机、阴影、噪点、模糊、低质量、变形、多余元素",
            size='512*512'
        )
        result = []
        if rsp.status_code != HTTPStatus.OK:
            raise
        for item in rsp.output.choices:
            image_url = item.message.content[0]['image']
            # 需要将 image_url 下载到本地临时文件，再上传到图床服务，然后删除本地临时文件
            image_file = os.path.join(temp_dir, f"logo.png")
            image_content = requests.get(image_url, stream=True).content
            open(image_file, "wb").write(image_content)
            if image_file:
                # 上传到图床服务
                new_image_url = upload_image_to_bed(image_file)
                # 删除本地临时文件
                os.remove(image_file)
                result.append(
                    ImageResource(
                        category=ImageTypeEnum.LOGO.value,
                        description=description,
                        image_url=new_image_url,
                    )
                )
        return result
    except Exception as e:
        logger.error(f"[image_tools] 生成 Logo 失败: {e}, prompt={logo_prompt}")
        return []
    finally:
        # 删除临时目录
        shutil.rmtree(temp_dir)


# ============ 工具集合 ============

ALL_IMAGE_TOOLS = [
    search_content_images,
    search_illustration_images,
    generate_architecture_image,
    generate_logo_image,
]
