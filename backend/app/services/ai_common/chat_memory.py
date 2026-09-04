"""
对话内存记忆管理模块

采用 "数据库持久化 + 内存缓存 + TTL过期 + Token裁剪" 的方案：
- 会话打开时从 DB 加载对话历史到内存
- 后续对话直接操作内存，定期/按需同步 DB
- 超限时按 Token 数裁剪，始终保留 system prompt
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from backend.app.common.emuns.chat_message_type import ChatMessageType
from backend.app.common.utils.estimate_tokens import estimate_tokens

logger = logging.getLogger(__name__)

# ==================== 配置 ====================

# 默认的上下文窗口 token 上限（根据具体模型调整，通义 qwen 系列通常 8k/32k/128k，这里是qwen-max最大128k）
DEFAULT_MAX_TOKENS = 1000000

# 每条 AI 回复的预留 token 数（避免对话历史占满窗口导致 AI 无输出空间）
DEFAULT_RESERVED_TOKENS_FOR_REPLY = 1000

# 内存缓存过期时间（秒），超过此时间未访问的会话将被淘汰
DEFAULT_MEMORY_TTL_SECONDS = 30 * 60  # 30 分钟

# 内存缓存最大会话数上限（防止内存泄漏）
DEFAULT_MAX_CACHED_SESSIONS = 100


# ==================== 数据结构 ====================

@dataclass
class MemoryMessage:
    """内存中的单条消息"""
    role: str          # 'system' | 'user' | 'assistant'
    content: str
    token_count: int = 0
    db_id: Optional[int] = None  # 对应数据库记录的 id（尚未入库则为 None）

    def to_llm_dict(self) -> Dict[str, str]:
        """转换为 LLM Chat API 需要的格式"""
        return {"role": self.role, "content": self.content}


@dataclass
class SessionMemory:
    """单个 app_id 对应的内存记忆"""
    app_id: int
    messages: List[MemoryMessage] = field(default_factory=list)
    last_access_time: float = field(default_factory=time.time)

    # ---------- 基础操作 ----------
    def add(self, role: str, content: str, token_count: int = 0, db_id: int = None) -> MemoryMessage:
        msg = MemoryMessage(role=role, content=content, token_count=token_count, db_id=db_id)
        self.messages.append(msg)
        self.last_access_time = time.time()
        return msg

    def touch(self):
        """刷新最近访问时间"""
        self.last_access_time = time.time()

    @property
    def total_tokens(self) -> int:
        return sum(m.token_count for m in self.messages)

    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """获取 LLM 可直接使用的消息列表"""
        return [m.to_llm_dict() for m in self.messages]

    def get_all(self) -> List[MemoryMessage]:
        self.touch()
        return list(self.messages)


# ==================== Token 裁剪 ====================

def trim_messages(
    messages: List[MemoryMessage],
    max_context_tokens: int = DEFAULT_MAX_TOKENS,
    reserved_for_reply: int = DEFAULT_RESERVED_TOKENS_FOR_REPLY,
) -> List[MemoryMessage]:
    """
    裁剪消息列表，确保总 token 不超过 (max_context_tokens - reserved_for_reply)

    裁剪策略：
    1. 始终保留所有 system 消息（system prompt 是根，不能丢）
    2. 从最旧的非 system 消息开始丢弃，直到总 token 满足条件
    3. 如果只剩 system 消息仍超限，则截断 system 消息内容（极端兜底）

    Args:
        messages: 待裁剪的消息列表
        max_context_tokens: 模型最大上下文 token
        reserved_for_reply: 为 AI 回复预留的 token 数

    Returns:
        裁剪后的消息列表（新列表，不修改原列表）
    """
    if not messages:
        return []

    allowed_tokens = max_context_tokens - reserved_for_reply
    if allowed_tokens <= 0:
        raise ValueError("max_context_tokens 必须大于 reserved_for_reply")

    result = list(messages)

    # 分离 system 消息与其他消息
    system_msgs = [m for m in result if m.role == "system"]
    other_msgs = [m for m in result if m.role != "system"]

    current_tokens = sum(m.token_count for m in result)

    # 从最旧的非 system 消息开始丢弃
    while current_tokens > allowed_tokens and other_msgs:
        discarded = other_msgs.pop(0)   # 最旧的非 system 消息
        current_tokens -= discarded.token_count
        logger.info(
            f"[ChatMemory] 裁剪超限 token，丢弃 app_id={discarded.db_id or 'unknown'} "
            f"的 {discarded.role} 消息 (tokens={discarded.token_count})"
        )

    trimmed = system_msgs + other_msgs
    new_total = sum(m.token_count for m in trimmed)

    # 极端兜底：system 消息本身就超限（截断最长的 system 消息）
    if new_total > allowed_tokens:
        logger.warning(
            f"[ChatMemory] 仅剩 system 消息仍超限 ({new_total} > {allowed_tokens})，"
            f"截断 system 消息内容"
        )
        # 找最长的 system 消息进行截断
        longest_system = max(system_msgs, key=lambda m: m.token_count)
        excess = new_total - allowed_tokens
        # 按比例缩减 content（中文字符近似等于 token，按字符数截断）
        keep_chars = max(50, len(longest_system.content) - int(excess))
        longest_system.content = longest_system.content[:keep_chars] + "\n...(system prompt truncated)"
        longest_system.token_count = estimate_tokens(longest_system.content)

    return trimmed


# ==================== ChatMemoryManager ====================

class ChatMemoryManager:
    """
    对话内存记忆管理器（线程安全，单例）

    使用方式：
        manager = ChatMemoryManager()  # 全局单例
        messages = manager.get_llm_messages(app_id)   # 自动缓存/加载/裁剪
        manager.add_message(app_id, "user", "你好", db_id=123)
        manager.evict_expired()                       # 定时清理
    """

    _instance: Optional["ChatMemoryManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        max_context_tokens: int = DEFAULT_MAX_TOKENS,
        reserved_for_reply: int = DEFAULT_RESERVED_TOKENS_FOR_REPLY,
        memory_ttl_seconds: int = DEFAULT_MEMORY_TTL_SECONDS,
        max_cached_sessions: int = DEFAULT_MAX_CACHED_SESSIONS,
    ):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._max_context_tokens = max_context_tokens
        self._reserved_for_reply = reserved_for_reply
        self._memory_ttl_seconds = memory_ttl_seconds
        self._max_cached_sessions = max_cached_sessions

        self._cache: Dict[int, SessionMemory] = {}
        self._cache_lock = threading.RLock()

    # ---------- 内部：DB 加载（Lazy Import 避免循环依赖） ----------
    def _load_from_db(self, app_id: int) -> SessionMemory:
        """
        从数据库加载指定会话的全部历史

        在方法内部延迟 import chat_history_service，避免模块级别的循环依赖问题：
        chat_memory.py → chat_history_service.py（service 层）→ model + db_instance
        chat_history_service.py 本身不依赖 chat_memory.py，所以无环。
        """
        session = SessionMemory(app_id=app_id)

        try:
            # 延迟 import：首次调用时才解析模块，此时所有模块都已加载完毕
            from backend.app.services.chat_history_service import (
                list_all_chat_history_by_app_id,
            )

            records = list_all_chat_history_by_app_id(app_id)
            # 按 create_time 升序排列（从旧到新）
            records = sorted(records, key=lambda r: r.get("create_time") or 0)

            type_to_role = {
                ChatMessageType.USER.value: "user",
                ChatMessageType.AI.value: "assistant",
                ChatMessageType.SYSTEM.value: "system",
            }

            for rec in records:
                role = type_to_role.get(rec.get("message_type"), "user")
                content = rec.get("message", "")
                token_count = rec.get("token_count") or estimate_tokens(content)
                db_id = rec.get("id")
                session.add(role=role, content=content, token_count=token_count, db_id=db_id)

            logger.info(f"[ChatMemory] 从 DB 加载 app_id={app_id} 共 {len(session.messages)} 条历史消息")
        except Exception as e:
            logger.error(f"[ChatMemory] 从 DB 加载 app_id={app_id} 失败: {e}")

        return session

    # ---------- 核心 API ----------
    def get_session(self, app_id: int) -> SessionMemory:
        """
        获取指定 app_id 的 SessionMemory（若缓存未命中则从 DB 加载）
        """
        with self._cache_lock:
            session = self._cache.get(app_id)
            if session is not None:
                session.touch()
                return session

            # 缓存 miss：从 DB 加载
            session = self._load_from_db(app_id)

            # LRU 淘汰：缓存已满时清理最久未访问的
            if len(self._cache) >= self._max_cached_sessions:
                self._evict_lru_one()

            self._cache[app_id] = session
            return session

    def get_llm_messages(self, app_id: int, extra_messages: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """
        获取裁剪好的、可直接传给 LLM 的完整消息列表

        Args:
            app_id: 应用 ID
            extra_messages: 额外需要追加的消息（例如当前用户的新输入），格式
                            [{"role": "user", "content": "..."}]

        Returns:
            [{"role": "...", "content": "..."}] 列表，已做 token 裁剪
        """
        session = self.get_session(app_id)

        # 合并 extra_messages（不写入 session，仅用于本次 LLM 调用）
        merged_messages = list(session.messages)
        if extra_messages:
            for em in extra_messages:
                merged_messages.append(MemoryMessage(
                    role=em["role"],
                    content=em["content"],
                    token_count=estimate_tokens(em["content"]),
                ))

        # 裁剪
        trimmed = trim_messages(
            merged_messages,
            max_context_tokens=self._max_context_tokens,
            reserved_for_reply=self._reserved_for_reply,
        )

        return [m.to_llm_dict() for m in trimmed]

    def add_message(
        self,
        app_id: int,
        role: str,
        content: str,
        db_id: Optional[int] = None,
        token_count: Optional[int] = None,
    ) -> MemoryMessage:
        """
        向指定会话追加一条内存消息

        注意：此方法**只写内存**，DB 持久化由外部调用方负责（避免 ChatMemoryManager 直接依赖 DB session）。
        如果 DB 写入后拿到了 id，可在稍后用 update_db_id() 回填。

        Args:
            app_id: 应用 ID
            role: 'system' | 'user' | 'assistant'
            content: 消息内容
            db_id: 数据库记录 ID（可选，DB 写入成功后回填）
            token_count: token 数（可选，不传则自动估算）
        """
        if role not in ("system", "user", "assistant"):
            raise ValueError(f"无效的 role: {role}")

        session = self.get_session(app_id)
        if token_count is None:
            token_count = estimate_tokens(content)
        msg = session.add(role=role, content=content, token_count=token_count, db_id=db_id)
        return msg

    def update_db_id(self, app_id: int, index: int, db_id: int):
        """
        回填某条内存消息的 db_id（DB 写入成功后调用）

        Args:
            app_id: 应用 ID
            index: 消息在 session.messages 中的下标
            db_id: 数据库记录主键
        """
        with self._cache_lock:
            session = self._cache.get(app_id)
            if session and 0 <= index < len(session.messages):
                session.messages[index].db_id = db_id

    def remove_message(self, app_id: int, index: int):
        """删除某条内存消息（一般用不到，主要用于测试/清理）"""
        with self._cache_lock:
            session = self._cache.get(app_id)
            if session and 0 <= index < len(session.messages):
                session.messages.pop(index)

    def clear_session(self, app_id: int):
        """清空并驱逐指定会话的内存缓存"""
        with self._cache_lock:
            self._cache.pop(app_id, None)
            logger.info(f"[ChatMemory] 已清空 app_id={app_id} 的内存记忆")

    # ---------- 缓存淘汰 ----------
    def evict_expired(self) -> int:
        """
        淘汰所有超过 TTL 的会话缓存

        Returns:
            实际淘汰的会话数量
        """
        now = time.time()
        with self._cache_lock:
            expired = [
                app_id for app_id, session in self._cache.items()
                if now - session.last_access_time > self._memory_ttl_seconds
            ]
            for app_id in expired:
                del self._cache[app_id]
            if expired:
                logger.info(f"[ChatMemory] TTL 淘汰 {len(expired)} 个会话: {expired}")
            return len(expired)

    def _evict_lru_one(self):
        """LRU 淘汰：驱逐最久未访问的一个会话"""
        with self._cache_lock:
            if not self._cache:
                return
            oldest_app_id = min(self._cache, key=lambda aid: self._cache[aid].last_access_time)
            del self._cache[oldest_app_id]
            logger.info(f"[ChatMemory] LRU 淘汰 app_id={oldest_app_id}")

    def clear_all(self):
        """清空全部内存缓存"""
        with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"[ChatMemory] 清空全部 {count} 个会话的内存记忆")

    # ---------- 状态查询 ----------
    def cache_info(self) -> Dict[str, Any]:
        """返回缓存状态信息（用于监控/调试）"""
        with self._cache_lock:
            return {
                "cached_sessions": len(self._cache),
                "max_cached_sessions": self._max_cached_sessions,
                "ttl_seconds": self._memory_ttl_seconds,
                "max_context_tokens": self._max_context_tokens,
                "sessions": [
                    {
                        "app_id": aid,
                        "messages_count": len(s.messages),
                        "total_tokens": s.total_tokens,
                        "idle_seconds": int(time.time() - s.last_access_time),
                    }
                    for aid, s in self._cache.items()
                ],
            }


# ==================== 便捷函数 ====================

def get_chat_memory_manager() -> ChatMemoryManager:
    """获取全局唯一的 ChatMemoryManager 实例"""
    return ChatMemoryManager()