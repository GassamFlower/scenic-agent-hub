"""
未命中问题跟踪。

当客服 Agent 无法回答用户问题时，自动记录至此队列。
运营人员可在管理后台查看并补充为知识库条目。
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class UnansweredTracker:
    """基于 SQLite 的未命中问题存储。"""

    def __init__(self, db_path: str = "data/unanswered.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._local = threading.local()
        self._init_tables()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_tables(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS unanswered (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                query       TEXT NOT NULL,
                intent      TEXT NOT NULL DEFAULT '',
                session_id  TEXT NOT NULL DEFAULT '',
                user_id     TEXT NOT NULL DEFAULT '',
                count       INTEGER NOT NULL DEFAULT 1,
                resolved    INTEGER NOT NULL DEFAULT 0,  -- 0=待处理 1=已处理
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def record(self, query: str, intent: str = "", session_id: str = "", user_id: str = "") -> None:
        """记录一条未命中问题（如已存在则增加计数）。"""
        # 找相似已存在的记录（相同或近似 query）
        row = self._conn.execute(
            "SELECT id, count FROM unanswered WHERE query = ? AND resolved = 0",
            (query,),
        ).fetchone()
        if row:
            self._conn.execute(
                "UPDATE unanswered SET count = count + 1 WHERE id = ?",
                (row["id"],),
            )
        else:
            self._conn.execute(
                "INSERT INTO unanswered (query, intent, session_id, user_id) VALUES (?, ?, ?, ?)",
                (query, intent, session_id, user_id),
            )
        self._conn.commit()

    def list_pending(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出待处理的未命中问题（按频次倒序）。"""
        rows = self._conn.execute(
            "SELECT * FROM unanswered WHERE resolved = 0 ORDER BY count DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_resolved(self, item_id: int) -> bool:
        cursor = self._conn.execute(
            "UPDATE unanswered SET resolved = 1, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (item_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def get(self, item_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("SELECT * FROM unanswered WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None


unanswered_tracker = UnansweredTracker()
