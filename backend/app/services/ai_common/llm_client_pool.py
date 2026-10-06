"""
LLM Client 实例池

解决 ChatClientBuilder.build() 开销大（ChatOpenAI 初始化 + 连接池预热几百ms）的问题。
基于已有的 MemoryCache 实现，按「配置签名」缓存 ChatClient 实例。

使用方式：
    builder = ChatClientBuilder().set_system_prompt("...").add_tools_by_names(["文件写入"])
    client = get_or_create(builder)   # 首次构建，后续全部命中缓存

设计原则：
    - ChatClient 构建后完全只读，线程安全，可多请求共享
    - 缓存 key 由「影响运行时行为的配置字段」生成，忽略等价的默认值差异
    - TTL 过期后自动销毁重建，规避极端情况下的连接池老化问题
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading

from backend.app.common.utils import MemoryCache
from .chat_client_builder import ChatClientBuilder

logger = logging.getLogger(__name__)


def _make_cache_key(builder: 'ChatClientBuilder', app_id: str) -> str:
    """
    从 ChatClientBuilder 的配置生成稳定的缓存 key，包含 app_id 以避免跨应用共享

    只选取影响 ChatClient 运行时行为的字段以及 app_id，忽略 api_key / base_url / timeout 等
    所有请求都相同的字段（它们都来自环境变量，不会因业务场景变化）。
    """
    # tools 部分：按名称排序后拼接，保证顺序不影响 key
    tool_names = []
    for t in builder.get_available_tools():
        name = getattr(t, 'name', None) or getattr(t, 'tool_name', None) or str(t)
        tool_names.append(name)
    tool_names.sort()
    fmt = builder.get_response_format()
    if fmt is None:
        response_fmt_key = None
    elif hasattr(fmt, '__qualname__'):
        response_fmt_key = f"{fmt.__module__}.{fmt.__qualname__}"
    elif isinstance(fmt, dict):
        response_fmt_key = json.dumps(fmt, sort_keys=True)
    else:
        response_fmt_key = str(fmt)

    key_parts = {
        'model': builder.get_model(),
        'system_prompt': builder.get_system_prompt() or '',
        'response_format': response_fmt_key,
        'tool_names': tool_names,
        'temperature': builder.get_temperature(),
        'top_p': builder.get_top_p(),
        'max_tokens': builder.get_max_tokens(),
        'app_id': app_id,
    }

    raw = json.dumps(key_parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


# -------------------- 缓存实例 --------------------
# ChatClient 实例池：默认最多 30 条（30 种不同配置已经足够），TTL 30 分钟
_LLM_CLIENT_CACHE: MemoryCache = MemoryCache(max_size=30, ttl_seconds=1800)
_LLM_CLIENT_CACHE.start_auto_evict()
# 并发保护：同一个 key 同时 miss 时只 build 一次
# _building_keys 现在存的是 Event 对象，而非简单的 set
# Event.set() 由 builder 在 build 完成后触发，唤醒所有等待者
_building_keys: dict[str, threading.Event] = {}
_lock = threading.Lock()
_BUILD_TIMEOUT_SECONDS = 60   # 单个 client build 最长等 60s，兜底


def get_or_create_chat_client(builder: 'ChatClientBuilder', app_id: str):
    cache_key = _make_cache_key(builder, app_id)

    # 缓存命中直接返回
    cached = _LLM_CLIENT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    is_builder = False

    with _lock:
        cached = _LLM_CLIENT_CACHE.get(cache_key)
        if cached is not None:              # 其他线程刚好 build 完成
            return cached

        wait_event = _building_keys.get(cache_key)
        if wait_event is None:
            wait_event = threading.Event()
            _building_keys[cache_key] = wait_event
            is_builder = True

    if not is_builder:
        finished = wait_event.wait(timeout=_BUILD_TIMEOUT_SECONDS)
        if not finished:
            logger.warning(
                f"[LLMClientPool] wait timeout ({_BUILD_TIMEOUT_SECONDS}s) "
                f"for key={cache_key[:8]}, fallback to rebuild"
            )
            # 超时兜底重试一次
            return get_or_create_chat_client(builder, app_id)

        cached = _LLM_CLIENT_CACHE.get(cache_key)
        if cached is not None:
            return cached
        # 罕见竞态：Event set 了但 cache 没 set 成功，重试
        return get_or_create_chat_client(builder, app_id)

    # build（无锁、可并发）
    try:
        client = builder.build()
        _LLM_CLIENT_CACHE.set(cache_key, client)
        logger.info(
            f"[LLMClientPool] 新建 ChatClient, key={cache_key}, "
            f"model={builder.get_model()}, tools={tool_names_str(builder)}"
        )
        return client
    except Exception:
        # build 失败也要清理，不然会永久卡住所有等待者
        logger.exception(f"[LLMClientPool] builder.build() failed, key={cache_key}")
        raise
    finally:
        with _lock:
            _building_keys.pop(cache_key, None)   # 清登记
        wait_event.set()   # 唤醒所有等待者（无论 build 成功还是失败）


def tool_names_str(builder: 'ChatClientBuilder') -> str:
    """调试辅助：把 builder 里注册的工具名拼成字符串"""
    names = []
    for t in builder.get_available_tools():
        name = getattr(t, 'name', None) or getattr(t, 'tool_name', None) or str(t)
        names.append(name)
    return ','.join(names) if names else '(none)'


def invalidate(builder: 'ChatClientBuilder', app_id: str) -> None:
    """
    主动让某个配置的缓存失效（一般不需要手动调用，TTL 自动清理）

    使用场景：极特殊情况下你确定某个 ChatClient 的状态已经不可用
    （例如底层 API_KEY 被热更新了）
    """
    cache_key = _make_cache_key(builder, app_id)
    _LLM_CLIENT_CACHE.delete(cache_key)
    logger.info(f"[LLMClientPool] 手动失效缓存, key={cache_key[:8]}")


def pool_info() -> dict:
    info = _LLM_CLIENT_CACHE.info()
    info['building_keys'] = list(_building_keys.keys())
    info['building_count'] = len(_building_keys)
    return info
