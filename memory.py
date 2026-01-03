from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Iterable, List, Optional


ALLOWED_ROLES = {"user", "assistant", "system"}


class MemoryManager:
    """Lightweight SQLite-backed chat history storage with optional TTL cleanup."""

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
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ttl_sec = self._normalize_ttl(ttl_sec)
        self._cleanup_interval_sec = self._normalize_interval(cleanup_interval_sec)
        self._last_cleanup_ts = 0.0
        self._init_db()
        self._maybe_cleanup(force=True)

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS chat_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "wx_id TEXT NOT NULL,"
                "role TEXT NOT NULL,"
                "content TEXT NOT NULL,"
                "created_at INTEGER NOT NULL"
                ")"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_wx_id_id "
                "ON chat_history (wx_id, id)"
            )
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

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
