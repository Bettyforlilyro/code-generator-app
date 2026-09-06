"""
通用线程安全内存缓存

支持：
    - TTL 过期淘汰：超过指定时间未访问的条目自动失效
    - 容量上限 + LRU 淘汰：缓存满时驱逐最久未访问的条目
    - 线程安全：所有公开方法内部加锁，多线程场景无需额外处理
    - 访问时间由 Cache 自身维护：对 value 对象无特殊接口要求

典型用途：
    - AI 对话历史缓存（ChatMemoryManager）
    - 用户会话信息缓存
    - 任何 "key → 对象" 形式的临时缓存场景

示例：
    cache = MemoryCache(max_size=100, ttl_seconds=1800)

    # 写入
    cache.set("user_123", {"name": "Alice", "role": "admin"})

    # 读取（命中时自动刷新访问时间）
    data = cache.get("user_123")
    if data is None:
        data = load_from_db("user_123")
        cache.set("user_123", data)

    # 定时清理（建议每 5-10 分钟调一次）
    cache.evict_expired()
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Generic, Iterator, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar("K")  # key 类型
V = TypeVar("V")  # value 类型

MAX_SIZE = 1000

TTL_SECONDS = 1800


class MemoryCache(Generic[K, V]):
    """
    线程安全的内存缓存（泛型）

    底层维护两个 dict：
        - _data:     {key: value} — 实际缓存内容
        - _access:   {key: last_access_timestamp} — 访问时间戳（用于 TTL 和 LRU）

    """

    def __init__(self, max_size: int = MAX_SIZE, ttl_seconds: int = TTL_SECONDS) -> None:
        """
        Args:
            max_size: 缓存最大条目数，0 表示不限制, 默认 1000
            ttl_seconds: 每条目的过期秒数，0 表示永不过期, 默认 1800 秒
        """
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._data: Dict[K, V] = {}
        self._access: Dict[K, float] = {}
        self._lock = threading.RLock()

        # 自动清理线程相关（延迟初始化，默认不启动）
        self._evict_thread: Optional[threading.Thread] = None
        self._evict_stop_event = threading.Event()

    # ---------- 核心读写 ----------

    def get(self, key: K) -> Optional[V]:
        """
        获取缓存值（命中时自动刷新访问时间）

        Args:
            key: 缓存键

        Returns:
            缓存值，未命中或已过期返回 None
        """
        with self._lock:
            if key not in self._data:
                return None

            # TTL 检查
            if self._is_expired(key):
                self._remove_no_lock(key)
                logger.debug(f"[MemoryCache] TTL 过期: {key}")
                return None

            # 命中，刷新访问时间
            self._access[key] = time.time()
            return self._data[key]

    def set(self, key: K, value: V) -> None:
        """
        写入缓存

        若已存在则覆盖；若已达容量上限则先驱逐一条 LRU 条目。

        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            # 已存在：直接覆盖并刷新访问时间
            if key in self._data:
                self._data[key] = value
                self._access[key] = time.time()
                return

            # 容量检查：满了先淘汰
            if 0 < self._max_size <= len(self._data):
                self._evict_lru_one()

            self._data[key] = value
            self._access[key] = time.time()

    def delete(self, key: K) -> None:
        """删除指定键"""
        with self._lock:
            self._remove_no_lock(key)

    def __contains__(self, key: K) -> bool:
        """支持 `key in cache` 语法"""
        return self.get(key) is not None

    def __len__(self) -> int:
        """支持 `len(cache)` 语法"""
        with self._lock:
            return len(self._data)

    # ---------- 批量清理 ----------

    def clear(self) -> None:
        """清空全部缓存"""
        with self._lock:
            count = len(self._data)
            self._data.clear()
            self._access.clear()
            logger.info(f"[MemoryCache] 清空全部 {count} 个条目")

    def evict_expired(self) -> int:
        """
        批量淘汰所有 TTL 过期的条目

        Returns:
            实际淘汰的条目数量
        """
        with self._lock:
            if self._ttl_seconds <= 0:
                return 0

            now = time.time()
            expired_keys = [
                k for k, ts in self._access.items()
                if now - ts > self._ttl_seconds
            ]
            for k in expired_keys:
                self._remove_no_lock(k)

            if expired_keys:
                logger.info(
                    f"[MemoryCache] TTL 淘汰 {len(expired_keys)} 个条目: {expired_keys[:10]}"
                    + ("..." if len(expired_keys) > 10 else "")
                )
            return len(expired_keys)

    # ---------- 状态查询 ----------

    def info(self) -> Dict[str, Any]:
        """返回缓存状态信息（监控 / 调试用）"""
        with self._lock:
            return {
                "size": len(self._data),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl_seconds,
                "keys": list(self._data.keys()),
            }

    def iter_items(self) -> Iterator[Tuple[K, V]]:
        """
        遍历所有缓存条目（快照，遍历时不影响锁状态）

        Returns:
            迭代 (key, value) 元组
        """
        with self._lock:
            snapshot = list(self._data.items())
        return iter(snapshot)

    # ---------- 内部辅助（必须在已持锁的上下文中调用） ----------

    def _is_expired(self, key: K) -> bool:
        """检查指定 key 是否已 TTL 过期（不持锁时调用不安全）"""
        if self._ttl_seconds <= 0:
            return False
        last_access = self._access.get(key, 0)
        return time.time() - last_access > self._ttl_seconds

    def _remove_no_lock(self, key: K) -> None:
        """移除条目（不持锁版本，调用方必须确保已持有 _lock）"""
        self._data.pop(key, None)
        self._access.pop(key, None)

    def _evict_lru_one(self) -> None:
        """LRU 淘汰：驱逐访问时间最早的一条（不持锁版本）"""
        if not self._access:
            return
        oldest_key = min(self._access, key=self._access.get)
        self._remove_no_lock(oldest_key)
        logger.debug(f"[MemoryCache] LRU 淘汰: {oldest_key}")

    # ---------- 自动清理线程 ----------

    def start_auto_evict(self, interval_seconds: Optional[int] = None) -> None:
        """
        启动后台守护线程，定期调用 self.evict_expired() 清理过期条目。

        线程为 daemon 线程，主进程退出时自动销毁，无需手动 stop。
        多次调用不会重复创建线程（幂等）。

        Args:
            interval_seconds: 清理间隔秒数。
                - 默认 ttl_seconds // 3（过期时间的 1/3，保证过期条目不会残留太久）
                - 若 ttl_seconds == 0（永不过期），默认 300 秒（纯容量上限场景下也周期性扫一下）
        """
        # 已经启动过了，直接返回（幂等）
        if self._evict_thread is not None and self._evict_thread.is_alive():
            return

        # 确定间隔
        if interval_seconds is None:
            if self._ttl_seconds > 0:
                interval_seconds = max(10, self._ttl_seconds // 3)
            else:
                interval_seconds = 300

        # 重置 stop 事件（支持 stop 后重新 start 的场景）
        self._evict_stop_event.clear()

        def _loop():
            # 第一次等一个间隔再清理，避免刚启动就立即扫一遍
            while not self._evict_stop_event.wait(interval_seconds):
                try:
                    self.evict_expired()
                except Exception as e:
                    logger.warning(f"[MemoryCache] 自动清理异常: {e}")

        self._evict_thread = threading.Thread(
            target=_loop,
            daemon=True,
            name=f"MemoryCache-Evict-{id(self)}",
        )
        self._evict_thread.start()
        logger.info(
            f"[MemoryCache] 自动清理线程已启动, interval={interval_seconds}s, "
            f"ttl={self._ttl_seconds}s"
        )

    def stop_auto_evict(self, timeout: float = 2.0) -> bool:
        """
        停止后台自动清理线程（一般不需要手动调，daemon 线程会随进程退出自动销毁）

        Args:
            timeout: 等待线程退出的超时秒数

        Returns:
            是否成功停止（False 表示线程不存在或已退出）
        """
        if self._evict_thread is None:
            return False
        self._evict_stop_event.set()       # 立即唤醒 wait
        self._evict_thread.join(timeout)   # 等待线程退出
        self._evict_thread = None
        logger.info("[MemoryCache] 自动清理线程已停止")
        return True

    @property
    def is_auto_evict_running(self) -> bool:
        """自动清理线程是否正在运行"""
        return self._evict_thread is not None and self._evict_thread.is_alive()