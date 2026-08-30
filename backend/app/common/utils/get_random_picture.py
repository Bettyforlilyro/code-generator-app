import os
import json
import logging
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv


logger = logging.getLogger(__name__)

load_dotenv()
API_BOX_DEV_ID = os.getenv("HZI_DEV_ID")
API_BOX_KEY = os.getenv("HZI_KEY")

API_BOX_AVATAR_URL = "https://cn.apihz.cn/api/img/apihzimgtx.php"
API_BOX_BZ_URL = "https://cn.apihz.cn/api/img/apihzimgbz.php"

# 获取失败时使用的默认头像（随机占位图）
DEFAULT_AVATAR = "https://picsum.photos/200/200"
DEFAULT_BZ = "https://picsum.photos/800/600"


def get_random_avatar() -> str:
    """
    调用 API 盒子接口获取随机头像 URL。

    接口文档:
        GET https://cn.apihz.cn/api/img/apihzimgtx.php
        参数: id (用户ID), key (用户KEY), type (1=JSON, 2=TXT)

    Returns:
        头像图片的 URL 字符串。调用失败时返回默认占位头像。
    """
    params = {
        "id": API_BOX_DEV_ID,
        "key": API_BOX_KEY,
        "type": 1,
    }
    url = f"{API_BOX_AVATAR_URL}?{urlencode(params)}"

    try:
        with urlopen(url, timeout=5) as response:
            raw = response.read().decode("utf-8")

        data = json.loads(raw)
        if data.get("code") == 200:
            avatar_url = data.get("msg")
            if avatar_url and avatar_url.startswith("http"):
                return avatar_url
        else:
            logger.warning("获取随机头像失败: %s", data.get("msg"))
    except (HTTPError, URLError, json.JSONDecodeError, Exception) as e:
        logger.warning("获取随机头像异常: %s", e)

    return DEFAULT_AVATAR


def get_random_bz() -> str:
    """
    调用 API 盒子接口获取随机封面 URL。

    接口文档:
        GET https://cn.apihz.cn/api/img/apihzimgbz.php
        参数: id (用户ID), key (用户KEY), type (1=JSON, 2=TXT)

    Returns:
        封面图片的 URL 字符串。调用失败时返回默认占位封面。
    """
    params = {
        "id": API_BOX_DEV_ID,
        "key": API_BOX_KEY,
        "type": 1,
        "imgtype": int(time.time()) % 3,    # 0是随机分类，1是综合大类，2是美女
    }
    url = f"{API_BOX_BZ_URL}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=5) as response:
            raw = response.read().decode("utf-8")

        data = json.loads(raw)
        if data.get("code") == 200:
            bz_url = data.get("msg")
            if bz_url and bz_url.startswith("http"):
                return bz_url
        else:
            logger.warning("获取随机封面失败: %s", data.get("msg"))
    except (HTTPError, URLError, json.JSONDecodeError, Exception) as e:
        logger.warning("获取随机封面异常: %s", e)

    return DEFAULT_BZ
