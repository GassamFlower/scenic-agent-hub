"""
会话记忆持久化存储。

使用 SQLite 实现按 session_id 维度的对话记忆持久化。
客户端只需传 session_id，服务端自动加载/保存历史对话。

升级路径:
- 当前: SQLite（零配置，单机持久化）
- 生产: 替换为 Redis（高并发）或 PostgreSQL（事务安全）
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List


class SessionStore:
    """基于 SQLite 的会话存储，线程安全。"""

    def __init__(self, db_path: str = "data/sessions.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._local = threading.local()
        self._init_tables()

    @property
    def _conn(self) -> sqlite3.Connection:
        """每个线程一个独立连接（SQLite 不支持跨线程共享连接）。"""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_tables(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL DEFAULT '',
                memory       TEXT NOT NULL DEFAULT '[]',
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def get_memory(self, session_id: str) -> List[Dict[str, str]]:
        """读取指定 session 的对话记忆。"""
        row = self._conn.execute(
            "SELECT memory FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return json.loads(row["memory"]) if row else []

    def save_memory(
        self, session_id: str, user_id: str, memory: List[Dict[str, str]]
    ) -> None:
        """写入/更新对话记忆。"""
        memory_json = json.dumps(memory, ensure_ascii=False)
        self._conn.execute(
            """
            INSERT INTO sessions (session_id, user_id, memory)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                memory = excluded.memory,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, user_id, memory_json),
        )
        self._conn.commit()

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出最近的会话（管理后台用）。"""
        rows = self._conn.execute(
            "SELECT session_id, user_id, updated_at FROM sessions "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


session_store = SessionStore()
