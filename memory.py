from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import List, Optional


ALLOWED_ROLES = {"user", "assistant", "system"}


class MemoryManager:
    """Lightweight SQLite-backed chat history storage."""

    def __init__(self, db_path: str = "chat_history.db") -> None:
        self.db_path = os.path.abspath(db_path)
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

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
        created_at = int(time.time())
        with self._lock:
            self._conn.execute(
                "INSERT INTO chat_history (wx_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (wx_id, role, content, created_at),
            )
            self._conn.commit()

    def get_recent_context(self, wx_id: str, limit: int = 20) -> List[dict]:
        wx_id = str(wx_id).strip()
        if not wx_id:
            return []
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
