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
from typing import TYPE_CHECKING

from backend.app.common.utils.cache import MemoryCache

if TYPE_CHECKING:
    from backend.app.services.ai_common.chat_client_builder import ChatClientBuilder

logger = logging.getLogger(__name__)

# -------------------- 缓存实例 --------------------
# ChatClient 实例池：默认最多 30 条（30 种不同配置已经足够），TTL 30 分钟
_LLM_CLIENT_CACHE: MemoryCache = MemoryCache(max_size=30, ttl_seconds=1800)
_LLM_CLIENT_CACHE.start_auto_evict()

# 并发保护：同一个 key 同时 miss 时只 build 一次
_building_keys: set[str] = set()
_lock = threading.Lock()


def _make_cache_key(builder: 'ChatClientBuilder') -> str:
    """
    从 ChatClientBuilder 的配置生成稳定的缓存 key

    只选取影响 ChatClient 运行时行为的字段，忽略 api_key / base_url / timeout 等
    所有请求都相同的字段（它们都来自环境变量，不会因业务场景变化）。
    """
    # tools 部分：按名称排序后拼接，保证顺序不影响 key
    tool_names = []
    for t in builder.get_available_tools():
        name = getattr(t, 'name', None) or getattr(t, 'tool_name', None) or str(t)
        tool_names.append(name)
    tool_names.sort()

    key_parts = {
        'model': builder.get_model(),
        'system_prompt': builder.get_system_prompt() or '',
        'response_format': (
            repr(builder.get_response_format())
            if builder.get_response_format() else None
        ),
        'tool_names': tool_names,
        # 以下字段理论上所有请求都相同，但为了严谨也纳入
        'temperature': builder.get_temperature(),
        'top_p': builder.get_top_p(),
        'max_tokens': builder.get_max_tokens(),
    }

    raw = json.dumps(key_parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def get_or_create(builder: 'ChatClientBuilder'):
    """
    从缓存池获取 ChatClient，未命中则构建并缓存

    Args:
        builder: 已配置好的 ChatClientBuilder

    Returns:
        ChatClient 实例

    线程安全：并发请求同一 key 时只 build 一次，其余请求等待结果返回
    """
    cache_key = _make_cache_key(builder)

    # 1. 快速路径：命中直接返回
    cached = _LLM_CLIENT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # 2. 并发保护：确保同一 key 只 build 一次
    with _lock:
        # double check：其他线程可能已经 build 好了
        cached = _LLM_CLIENT_CACHE.get(cache_key)
        if cached is not None:
            return cached

        # 标记正在构建，其他线程等待 build 完后走快速路径
        if cache_key in _building_keys:
            # 理论上不会走到这里（上面的 get 已经 double check 过了）
            # 防御性：短暂阻塞后重试
            import time
            time.sleep(0.05)
            cached = _LLM_CLIENT_CACHE.get(cache_key)
            if cached is not None:
                return cached

        _building_keys.add(cache_key)
        try:
            # 3. 构建（慢路径，几百ms）
            client = builder.build()
            _LLM_CLIENT_CACHE.set(cache_key, client)
            logger.info(f"[LLMClientPool] 新建 ChatClient, key={cache_key[:8]}, "
                        f"model={builder.get_model()}, tools={tool_names_str(builder)}")
            return client
        finally:
            _building_keys.discard(cache_key)


def tool_names_str(builder: 'ChatClientBuilder') -> str:
    """调试辅助：把 builder 里注册的工具名拼成字符串"""
    names = []
    for t in builder.get_available_tools():
        name = getattr(t, 'name', None) or getattr(t, 'tool_name', None) or str(t)
        names.append(name)
    return ','.join(names) if names else '(none)'


def invalidate(builder: 'ChatClientBuilder') -> None:
    """
    主动让某个配置的缓存失效（一般不需要手动调用，TTL 自动清理）

    使用场景：极特殊情况下你确定某个 ChatClient 的状态已经不可用
    （例如底层 API_KEY 被热更新了）
    """
    cache_key = _make_cache_key(builder)
    _LLM_CLIENT_CACHE.delete(cache_key)
    logger.info(f"[LLMClientPool] 手动失效缓存, key={cache_key[:8]}")


def pool_info() -> dict:
    """返回池子的状态信息（监控 / 调试用）"""
    info = _LLM_CLIENT_CACHE.info()
    info['building_keys'] = list(_building_keys)
    return info
