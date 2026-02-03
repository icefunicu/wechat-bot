"""
聊天记忆管理模块 - 基于 aiosqlite 的异步持久化存储。

本模块提供了轻量级的聊天历史和用户画像管理功能：
- 按会话存储用户/助手消息历史
- 支持 TTL 自动清理过期记录
- 用户画像管理（昵称、关系、偏好、事实记忆）
- 情绪历史记录

主要类:
    MemoryManager: 核心管理器类，封装了所有数据库操作

使用示例:
    manager = MemoryManager("chat_history.db")
    await manager.add_message("user_123", "user", "你好！")
    context = await manager.get_recent_context("user_123", limit=10)
    await manager.close()
"""

from __future__ import annotations

import json
import os
import time
import copy
import asyncio
import aiosqlite
from typing import Any, Dict, Iterable, List, Optional, Tuple
from ..schemas import UserProfile

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
    基于 aiosqlite 的异步聊天历史存储管理器。
    
    支持消息历史存储、用户画像管理、TTL 自动清理等功能。
    
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
        self._conn: Optional[aiosqlite.Connection] = None
        self._ttl_sec = self._normalize_ttl(ttl_sec)
        self._cleanup_interval_sec = self._normalize_interval(cleanup_interval_sec)
        self._last_cleanup_ts = 0.0
        self._init_lock = asyncio.Lock() # 防止并发初始化

    async def __aenter__(self) -> "MemoryManager":
        """异步上下文管理器入口。"""
        await self._get_db()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口，自动关闭连接。"""
        await self.close()

    async def _get_db(self) -> aiosqlite.Connection:
        """获取数据库连接（懒加载）"""
        if self._conn:
            return self._conn
            
        async with self._init_lock:
            if self._conn:
                return self._conn
                
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
                
            self._conn = await aiosqlite.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = aiosqlite.Row
            await self._init_tables()
            return self._conn

    async def _init_tables(self) -> None:
        """初始化数据库表结构"""
        if not self._conn:
            return
            
        # 聊天历史表
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS chat_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "wx_id TEXT NOT NULL,"
            "role TEXT NOT NULL,"
            "content TEXT NOT NULL,"
            "created_at INTEGER NOT NULL"
            ")"
        )
        # 索引：按 wx_id 和 id 查询（用于获取最近消息）
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_history_wx_id_id "
            "ON chat_history (wx_id, id)"
        )
        # 索引：按 created_at 查询（用于 TTL 清理，大幅提升清理性能）
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_history_created_at "
            "ON chat_history (created_at)"
        )
        # 用户画像表
        await self._conn.execute(
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
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_updated_at "
            "ON user_profiles (updated_at)"
        )
        # 启用 WAL 模式提升并发性能
        await self._conn.execute("PRAGMA journal_mode=WAL")
        # 启用 synchronous = NORMAL (WAL模式下安全且更快)
        await self._conn.execute("PRAGMA synchronous = NORMAL")
        # 将临时表存储在内存中
        await self._conn.execute("PRAGMA temp_store = MEMORY")
        # 启用内存映射 I/O 提升读取性能
        await self._conn.execute("PRAGMA mmap_size=268435456")
        await self._conn.commit()

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

    async def update_retention(
        self,
        ttl_sec: Optional[float],
        cleanup_interval_sec: Optional[float] = None,
    ) -> None:
        self._ttl_sec = self._normalize_ttl(ttl_sec)
        if cleanup_interval_sec is not None:
            self._cleanup_interval_sec = self._normalize_interval(
                cleanup_interval_sec
            )
        await self._maybe_cleanup(force=True)

    async def _maybe_cleanup(self, force: bool = False) -> None:
        if not self._ttl_sec:
            return
        now = time.time()
        if not force and self._cleanup_interval_sec > 0:
            if now - self._last_cleanup_ts < self._cleanup_interval_sec:
                return
        cutoff = int(now - self._ttl_sec)
        if cutoff <= 0:
            return
            
        db = await self._get_db()
        await db.execute(
            "DELETE FROM chat_history WHERE created_at < ?",
            (cutoff,),
        )
        await db.commit()
        self._last_cleanup_ts = now

    async def has_messages(self, wx_id: str) -> bool:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return False
        await self._maybe_cleanup()
        
        db = await self._get_db()
        async with db.execute(
            "SELECT 1 FROM chat_history WHERE wx_id = ? LIMIT 1",
            (wx_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row is not None

    async def add_message(self, wx_id: str, role: str, content: str) -> None:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return
        role = str(role).strip().lower()
        if role not in ALLOWED_ROLES:
            raise ValueError(f"Unsupported role: {role}")
        content = str(content or "").strip()
        if not content:
            return
        await self._maybe_cleanup()
        created_at = int(time.time())
        
        db = await self._get_db()
        await db.execute(
            "INSERT INTO chat_history (wx_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (wx_id, role, content, created_at),
        )
        await db.commit()

    async def add_messages(self, wx_id: str, messages: Iterable[dict]) -> int:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return 0
        await self._maybe_cleanup()
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
            
        db = await self._get_db()
        await db.executemany(
            "INSERT INTO chat_history (wx_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        await db.commit()
        return len(rows)

    async def get_recent_context(self, wx_id: str, limit: int = 20) -> List[dict]:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return []
        await self._maybe_cleanup()
        try:
            limit_val = int(limit)
        except (TypeError, ValueError):
            limit_val = 20
        if limit_val <= 0:
            return []
            
        db = await self._get_db()
        async with db.execute(
            "SELECT role, content FROM chat_history "
            "WHERE wx_id = ? ORDER BY id DESC LIMIT ?",
            (wx_id, limit_val),
        ) as cursor:
            rows = await cursor.fetchall()
            
        context: List[dict] = []
        for row in reversed(rows):
            content = row["content"]
            if not content:
                continue
            context.append({"role": row["role"], "content": content})
        return context

    async def get_global_recent_messages(self, limit: int = 50) -> List[dict]:
        """
        获取全局最近消息历史（跨所有会话）。
        """
        try:
            limit_val = int(limit)
        except (TypeError, ValueError):
            limit_val = 50
        
        if limit_val <= 0:
            return []
            
        db = await self._get_db()
        
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
        async with db.execute(sql, (limit_val,)) as cursor:
            rows = await cursor.fetchall()
            
        messages = []
        for row in reversed(rows):
            msg = {
                "id": row["id"],
                "wx_id": row["wx_id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["created_at"],
                "sender": row["nickname"] or row["wx_id"],
                "is_self": row["role"] == "assistant"
            }
            messages.append(msg)
            
        return messages

    # ==================== 用户画像方法 ====================

    async def get_user_profile(self, wx_id: str) -> UserProfile:
        """获取用户画像，如果不存在则返回默认画像"""
        wx_id = str(wx_id).strip()
        if not wx_id:
            return UserProfile(wx_id=wx_id, **DEFAULT_USER_PROFILE)
            
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM user_profiles WHERE wx_id = ?",
            (wx_id,),
        ) as cursor:
            row = await cursor.fetchone()
            
        if row is None:
            return UserProfile(wx_id=wx_id, **DEFAULT_USER_PROFILE)
            
        data = dict(DEFAULT_USER_PROFILE)
        data['wx_id'] = wx_id
        
        data["nickname"] = row["nickname"] or ""
        data["relationship"] = row["relationship"] or "unknown"
        data["personality"] = row["personality"] or ""
        data["last_emotion"] = row["last_emotion"] or "neutral"
        data["message_count"] = row["message_count"] or 0
        data["updated_at"] = row["updated_at"] or 0

        # 解析 JSON 字段
        try:
            data["preferences"] = json.loads(row["preferences"] or "{}")
        except (json.JSONDecodeError, TypeError):
            data["preferences"] = {}
        try:
            data["context_facts"] = json.loads(row["context_facts"] or "[]")
        except (json.JSONDecodeError, TypeError):
            data["context_facts"] = []
        try:
            data["emotion_history"] = json.loads(row["emotion_history"] or "[]")
        except (json.JSONDecodeError, TypeError):
            data["emotion_history"] = []
            
        return UserProfile(**data)

    async def _ensure_user_profile(self, wx_id: str) -> None:
        """确保用户画像存在，不存在则创建"""
        db = await self._get_db()
        await db.execute(
            "INSERT OR IGNORE INTO user_profiles (wx_id, updated_at) VALUES (?, ?)",
            (wx_id, int(time.time())),
        )
        await db.commit()

    async def update_user_profile(self, wx_id: str, **fields: Any) -> None:
        """
        更新用户画像的指定字段。
        """
        wx_id = str(wx_id).strip()
        if not wx_id:
            return
        await self._ensure_user_profile(wx_id)
        
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
        db = await self._get_db()
        await db.execute(sql, values)
        await db.commit()

    async def add_context_fact(self, wx_id: str, fact: str, max_facts: int = 20) -> None:
        """添加一条事实信息到用户画像"""
        wx_id = str(wx_id).strip()
        fact = str(fact).strip()
        if not wx_id or not fact:
            return
            
        profile = await self.get_user_profile(wx_id)
        facts = list(profile.context_facts) # Use attribute access
        
        # 避免重复
        if fact not in facts:
            facts.append(fact)
            # 限制数量
            if len(facts) > max_facts:
                facts = facts[-max_facts:]
            await self.update_user_profile(wx_id, context_facts=facts)

    async def update_emotion(
        self, wx_id: str, emotion: str, max_history: int = 10
    ) -> None:
        """更新用户的当前情绪，并记录到历史"""
        wx_id = str(wx_id).strip()
        emotion = str(emotion).strip().lower()
        if not wx_id or not emotion:
            return
            
        profile = await self.get_user_profile(wx_id)
        history = list(profile.emotion_history) # Use attribute access
        
        history.append({"emotion": emotion, "timestamp": int(time.time())})
        if len(history) > max_history:
            history = history[-max_history:]
        await self.update_user_profile(
            wx_id, last_emotion=emotion, emotion_history=history
        )

    async def increment_message_count(self, wx_id: str) -> int:
        """增加用户消息计数并返回新值"""
        wx_id = str(wx_id).strip()
        if not wx_id:
            return 0
        await self._ensure_user_profile(wx_id)
        
        db = await self._get_db()
        await db.execute(
            "UPDATE user_profiles SET message_count = message_count + 1, "
            "updated_at = ? WHERE wx_id = ?",
            (int(time.time()), wx_id),
        )
        await db.commit()
        
        async with db.execute(
            "SELECT message_count FROM user_profiles WHERE wx_id = ?",
            (wx_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["message_count"] if row else 0

    async def close(self) -> None:
        if self._conn:
            try:
                await self._conn.close()
            except Exception:
                pass
            self._conn = None
