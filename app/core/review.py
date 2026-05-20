"""
人工审核队列。

当 require_human_review=True 时，业务节点的输出会暂存到审核队列，
运营人员可通过 API 查看待审列表并完成审核。

数据流:
  hitl_gate 节点 -> ReviewQueue.submit() -> 审核记录入库
  运营人员 GET /reviews -> 查看待审列表
  运营人员 POST /reviews/{id}/complete -> 完成审核

升级路径:
- 当前: SQLite（简单可用）
- 生产: PostgreSQL + 消息队列（如 RabbitMQ）实现异步通知
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ReviewQueue:
    """基于 SQLite 的人工审核队列。"""

    def __init__(self, db_path: str = "data/reviews.db"):
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
            CREATE TABLE IF NOT EXISTS reviews (
                review_id       TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL DEFAULT '',
                user_id         TEXT NOT NULL DEFAULT '',
                query           TEXT NOT NULL,
                agent_response  TEXT NOT NULL DEFAULT '',
                intent          TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'pending',
                reviewer_note   TEXT NOT NULL DEFAULT '',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at     TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def submit(
        self,
        session_id: str,
        user_id: str,
        query: str,
        agent_response: str,
        intent: str,
    ) -> str:
        """提交审核请求，返回 review_id。"""
        review_id = f"REV-{uuid4().hex[:10].upper()}"
        self._conn.execute(
            """
            INSERT INTO reviews
                (review_id, session_id, user_id, query, agent_response, intent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (review_id, session_id, user_id, query, agent_response, intent),
        )
        self._conn.commit()
        return review_id

    def list_pending(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出待审核项。"""
        rows = self._conn.execute(
            "SELECT * FROM reviews WHERE status = 'pending' "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, review_id: str) -> Optional[Dict[str, Any]]:
        """获取单条审核记录。"""
        row = self._conn.execute(
            "SELECT * FROM reviews WHERE review_id = ?", (review_id,)
        ).fetchone()
        return dict(row) if row else None

    def complete(
        self, review_id: str, approved: bool, reviewer_note: str = ""
    ) -> bool:
        """完成审核。"""
        status = "approved" if approved else "rejected"
        cursor = self._conn.execute(
            """
            UPDATE reviews SET
                status = ?, reviewer_note = ?, reviewed_at = ?
            WHERE review_id = ? AND status = 'pending'
            """,
            (status, reviewer_note, datetime.utcnow().isoformat(), review_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0


review_queue = ReviewQueue()
