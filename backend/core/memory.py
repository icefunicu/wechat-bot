"""
聊天记忆管理模块 - 基于 SQLite 的持久化存储。

本模块提供了轻量级的聊天历史和用户画像管理功能：
- 按会话存储用户/助手消息历史
- 支持 TTL 自动清理过期记录
- 用户画像管理（昵称、关系、偏好、事实记忆）
- 情绪历史记录

主要类:
    MemoryManager: 核心管理器类，封装了所有数据库操作

使用示例:
    >>> manager = MemoryManager("chat_history.db")
    >>> manager.add_message("user_123", "user", "你好！")
    >>> context = manager.get_recent_context("user_123", limit=10)
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import copy
from typing import Any, Dict, Iterable, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
#                               常量定义
# ═══════════════════════════════════════════════════════════════════════════════

# 使用 frozenset 加速成员检查（O(1) 复杂度）
ALLOWED_ROLES: frozenset = frozenset({"user", "assistant", "system"})

# JSON 字段集合（优化 update_user_profile 中的字段类型检查）
_JSON_FIELDS: frozenset = frozenset({"preferences", "context_facts", "emotion_history"})

# 默认用户画像模板
DEFAULT_USER_PROFILE = {
    "nickname": "",
    "relationship": "unknown",  # unknown/friend/close_friend/family/colleague/stranger
    "personality": "",
    "preferences": {},  # {"topics": [], "style": "", "likes": [], "dislikes": []}
    "context_facts": [],  # ["生日是5月1日", "喜欢猫", ...]
    "last_emotion": "neutral",
    "emotion_history": [],  # 最近 N 次情绪记录
    "message_count": 0,
}


# ═══════════════════════════════════════════════════════════════════════════════
#                               记忆管理器类
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryManager:
    """
    基于 SQLite 的轻量级聊天历史存储管理器。
    
    支持消息历史存储、用户画像管理、TTL 自动清理等功能。
    线程安全，可在多线程环境中使用。
    
    支持上下文管理器协议：
        with MemoryManager("chat.db") as manager:
            manager.add_message(...)
    
    Attributes:
        db_path (str): SQLite 数据库文件路径
    """
    
    # 允许更新的用户画像字段（使用 frozenset 加速查找）
    _ALLOWED_PROFILE_FIELDS: frozenset = frozenset({
        "nickname", "relationship", "personality", "preferences",
        "context_facts", "last_emotion", "emotion_history", "message_count"
    })

    def __init__(
        self,
        db_path: str = "chat_history.db",
        ttl_sec: Optional[float] = None,
        cleanup_interval_sec: float = 300.0,
    ) -> None:
        self.db_path = os.path.abspath(db_path)
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ttl_sec = self._normalize_ttl(ttl_sec)
        self._cleanup_interval_sec = self._normalize_interval(cleanup_interval_sec)
        self._last_cleanup_ts = 0.0
        self._init_db()
        self._maybe_cleanup(force=True)

    def __enter__(self) -> "MemoryManager":
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口，自动关闭连接。"""
        self.close()
        return None

    def _init_db(self) -> None:
        with self._lock:
            # 聊天历史表
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS chat_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "wx_id TEXT NOT NULL,"
                "role TEXT NOT NULL,"
                "content TEXT NOT NULL,"
                "created_at INTEGER NOT NULL"
                ")"
            )
            # 索引：按 wx_id 和 id 查询（用于获取最近消息）
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_wx_id_id "
                "ON chat_history (wx_id, id)"
            )
            # 索引：按 created_at 查询（用于 TTL 清理，大幅提升清理性能）
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_created_at "
                "ON chat_history (created_at)"
            )
            # 用户画像表
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS user_profiles ("
                "wx_id TEXT PRIMARY KEY,"
                "nickname TEXT DEFAULT '',"
                "relationship TEXT DEFAULT 'unknown',"
                "personality TEXT DEFAULT '',"
                "preferences TEXT DEFAULT '{}',"
                "context_facts TEXT DEFAULT '[]',"
                "last_emotion TEXT DEFAULT 'neutral',"
                "emotion_history TEXT DEFAULT '[]',"
                "message_count INTEGER DEFAULT 0,"
                "updated_at INTEGER NOT NULL"
                ")"
            )
            # 索引：按 updated_at 查询（用于活跃用户排序）
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_profiles_updated_at "
                "ON user_profiles (updated_at)"
            )
            # 启用 WAL 模式提升并发性能
            self._conn.execute("PRAGMA journal_mode=WAL")
            # 启用 synchronous = NORMAL (WAL模式下安全且更快)
            self._conn.execute("PRAGMA synchronous = NORMAL")
            # 将临时表存储在内存中
            self._conn.execute("PRAGMA temp_store = MEMORY")
            # 启用内存映射 I/O 提升读取性能
            self._conn.execute("PRAGMA mmap_size=268435456")
            self._conn.commit()

    @staticmethod
    def _normalize_ttl(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            val = float(value)
        except (TypeError, ValueError):
            return None
        if val <= 0:
            return None
        return val

    @staticmethod
    def _normalize_interval(value: Optional[float]) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, val)

    def update_retention(
        self,
        ttl_sec: Optional[float],
        cleanup_interval_sec: Optional[float] = None,
    ) -> None:
        self._ttl_sec = self._normalize_ttl(ttl_sec)
        if cleanup_interval_sec is not None:
            self._cleanup_interval_sec = self._normalize_interval(
                cleanup_interval_sec
            )
        self._maybe_cleanup(force=True)

    def _maybe_cleanup(self, force: bool = False) -> None:
        if not self._ttl_sec:
            return
        now = time.time()
        if not force and self._cleanup_interval_sec > 0:
            if now - self._last_cleanup_ts < self._cleanup_interval_sec:
                return
        cutoff = int(now - self._ttl_sec)
        if cutoff <= 0:
            return
        with self._lock:
            self._conn.execute(
                "DELETE FROM chat_history WHERE created_at < ?",
                (cutoff,),
            )
            self._conn.commit()
        self._last_cleanup_ts = now

    def has_messages(self, wx_id: str) -> bool:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return False
        self._maybe_cleanup()
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM chat_history WHERE wx_id = ? LIMIT 1",
                (wx_id,),
            ).fetchone()
        return row is not None

    def add_message(self, wx_id: str, role: str, content: str) -> None:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return
        role = str(role).strip().lower()
        if role not in ALLOWED_ROLES:
            raise ValueError(f"Unsupported role: {role}")
        content = str(content or "").strip()
        if not content:
            return
        self._maybe_cleanup()
        created_at = int(time.time())
        with self._lock:
            self._conn.execute(
                "INSERT INTO chat_history (wx_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (wx_id, role, content, created_at),
            )
            self._conn.commit()

    def add_messages(self, wx_id: str, messages: Iterable[dict]) -> int:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return 0
        self._maybe_cleanup()
        created_at = int(time.time())
        rows = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "")).strip().lower()
            if role not in ALLOWED_ROLES:
                continue
            content = str(msg.get("content", "") or "").strip()
            if not content:
                continue
            rows.append((wx_id, role, content, created_at))
        if not rows:
            return 0
        with self._lock:
            self._conn.executemany(
                "INSERT INTO chat_history (wx_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()
        return len(rows)

    def get_recent_context(self, wx_id: str, limit: int = 20) -> List[dict]:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return []
        self._maybe_cleanup()
        try:
            limit_val = int(limit)
        except (TypeError, ValueError):
            limit_val = 20
        if limit_val <= 0:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM chat_history "
                "WHERE wx_id = ? ORDER BY id DESC LIMIT ?",
                (wx_id, limit_val),
            ).fetchall()
        context: List[dict] = []
        for row in reversed(rows):
            content = row["content"]
            if not content:
                continue
            context.append({"role": row["role"], "content": content})
        return context

    def get_global_recent_messages(self, limit: int = 50) -> List[dict]:
        """
        获取全局最近消息历史（跨所有会话）。
        
        Args:
            limit: 返回条数限制
            
        Returns:
            包含完整消息信息的列表:
            [
                {
                    "id": 1,
                    "wx_id": "wxid_...",
                    "role": "user",
                    "content": "消息内容",
                    "created_at": 1234567890
                },
                ...
            ]
        """
        try:
            limit_val = int(limit)
        except (TypeError, ValueError):
            limit_val = 50
        
        if limit_val <= 0:
            return []
            
        with self._lock:
            # 联表查询获取昵称（可选，这里先只查历史表，前端可能需要 sender name）
            # 为了性能，这里先只查 chat_history，如果需要昵称，前端可以根据 wx_id 缓存
            # 或者我们在这里 join user_profiles
            
            # 使用 left join 获取 nickname
            sql = """
                SELECT 
                    h.id, h.wx_id, h.role, h.content, h.created_at,
                    u.nickname, u.relationship
                FROM chat_history h
                LEFT JOIN user_profiles u ON h.wx_id = u.wx_id
                ORDER BY h.id DESC
                LIMIT ?
            """
            rows = self._conn.execute(sql, (limit_val,)).fetchall()
            
        messages = []
        # Reverse to chronological order (oldest first) ? 
        # Usually web chat UI wants newest at bottom. 
        # API gets desc (newest first), app.js renders. 
        # If app.js prepends, we want newest first. If it appends, we want oldest first.
        # app.js renderMessages simple map.
        # Usually list APIs return sorted by time desc or asc.
        # Let's return sorted by time ASC (chronological) for chat view consistency.
        
        for row in reversed(rows):
            msg = {
                "id": row["id"],
                "wx_id": row["wx_id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["created_at"],
                "sender": row["nickname"] or row["wx_id"], # Fallback to wx_id if no nickname
                "is_self": row["role"] == "assistant"
            }
            messages.append(msg)
            
        return messages

    # ==================== 用户画像方法 ====================

    def get_user_profile(self, wx_id: str) -> Dict[str, Any]:
        """获取用户画像，如果不存在则返回默认画像"""
        wx_id = str(wx_id).strip()
        if not wx_id:
            return copy.deepcopy(DEFAULT_USER_PROFILE)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM user_profiles WHERE wx_id = ?",
                (wx_id,),
            ).fetchone()
        if row is None:
            return copy.deepcopy(DEFAULT_USER_PROFILE)
            
        # 这里虽然用了 dict() 浅拷贝，但在后续会重新赋值所有可变字段（preferences 等），
        # 所以对于数据库中存在的用户，不存在共享引用问题。
        # 但为了一致性和安全性，建议也使用 deepcopy 或显式构建。
        profile = copy.deepcopy(DEFAULT_USER_PROFILE)
        
        profile["nickname"] = row["nickname"] or ""
        profile["relationship"] = row["relationship"] or "unknown"
        profile["personality"] = row["personality"] or ""
        profile["last_emotion"] = row["last_emotion"] or "neutral"
        profile["message_count"] = row["message_count"] or 0
        # 解析 JSON 字段
        try:
            profile["preferences"] = json.loads(row["preferences"] or "{}")
        except (json.JSONDecodeError, TypeError):
            profile["preferences"] = {}
        try:
            profile["context_facts"] = json.loads(row["context_facts"] or "[]")
        except (json.JSONDecodeError, TypeError):
            profile["context_facts"] = []
        try:
            profile["emotion_history"] = json.loads(row["emotion_history"] or "[]")
        except (json.JSONDecodeError, TypeError):
            profile["emotion_history"] = []
        return profile

    def _ensure_user_profile(self, wx_id: str) -> None:
        """确保用户画像存在，不存在则创建"""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO user_profiles (wx_id, updated_at) VALUES (?, ?)",
                (wx_id, int(time.time())),
            )
            self._conn.commit()

    def update_user_profile(self, wx_id: str, **fields: Any) -> None:
        """
        更新用户画像的指定字段。
        
        只允许更新预定义的字段，JSON 字段会自动序列化。
        """
        wx_id = str(wx_id).strip()
        if not wx_id:
            return
        self._ensure_user_profile(wx_id)
        
        updates: List[str] = []
        values: List[Any] = []
        
        for key, value in fields.items():
            if key not in self._ALLOWED_PROFILE_FIELDS:
                continue
            # JSON 字段需要序列化
            if key in _JSON_FIELDS:
                value = json.dumps(value, ensure_ascii=False)
            updates.append(f"{key} = ?")
            values.append(value)
        
        if not updates:
            return
        
        updates.append("updated_at = ?")
        values.append(int(time.time()))
        values.append(wx_id)
        
        sql = f"UPDATE user_profiles SET {', '.join(updates)} WHERE wx_id = ?"
        with self._lock:
            self._conn.execute(sql, values)
            self._conn.commit()

    def add_context_fact(self, wx_id: str, fact: str, max_facts: int = 20) -> None:
        """添加一条事实信息到用户画像"""
        wx_id = str(wx_id).strip()
        fact = str(fact).strip()
        if not wx_id or not fact:
            return
        with self._lock:
            profile = self.get_user_profile(wx_id)
            facts = profile.get("context_facts", [])
            if not isinstance(facts, list):
                facts = []
            # 避免重复
            if fact not in facts:
                facts.append(fact)
                # 限制数量
                if len(facts) > max_facts:
                    facts = facts[-max_facts:]
                self.update_user_profile(wx_id, context_facts=facts)

    def update_emotion(
        self, wx_id: str, emotion: str, max_history: int = 10
    ) -> None:
        """更新用户的当前情绪，并记录到历史"""
        wx_id = str(wx_id).strip()
        emotion = str(emotion).strip().lower()
        if not wx_id or not emotion:
            return
        with self._lock:
            profile = self.get_user_profile(wx_id)
            history = profile.get("emotion_history", [])
            if not isinstance(history, list):
                history = []
            history.append({"emotion": emotion, "timestamp": int(time.time())})
            if len(history) > max_history:
                history = history[-max_history:]
            self.update_user_profile(
                wx_id, last_emotion=emotion, emotion_history=history
            )

    def increment_message_count(self, wx_id: str) -> int:
        """增加用户消息计数并返回新值"""
        wx_id = str(wx_id).strip()
        if not wx_id:
            return 0
        self._ensure_user_profile(wx_id)
        with self._lock:
            self._conn.execute(
                "UPDATE user_profiles SET message_count = message_count + 1, "
                "updated_at = ? WHERE wx_id = ?",
                (int(time.time()), wx_id),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT message_count FROM user_profiles WHERE wx_id = ?",
                (wx_id,),
            ).fetchone()
        return row["message_count"] if row else 0

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
