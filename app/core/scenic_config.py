"""
景区配置管理。

存储景区运营参数（开放时间、门票价格、地址、联系方式、购票链接等），
可在管理后台直接修改，Agent 回复时自动使用最新配置。

配置项均为 key-value 键值对，支持增改查。
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


# 默认配置项（首次初始化时写入）
DEFAULT_CONFIGS: Dict[str, str] = {
    "scenic_name": "门神文化景区",
    "opening_hours": "每日 08:30 - 17:30（夏季延长至 18:00），全年无休（除夕闭馆）",
    "ticket_adult_price": "¥68/张",
    "ticket_student_price": "¥38/张（需持学生证）",
    "ticket_free": "60 岁以上老人免票（需持身份证）",
    "address": "湖北省武汉市黄陂区门神文化大道 1 号",
    "phone": "027-12345678",
    "complaint_phone": "027-12345679",
    "purchase_link": "https://mp.weixin.qq.com/（门神文化景区小程序）",
    "traffic_guide": "地铁 2 号线至「门神站」A 口出站步行 5 分钟；自驾导航「门神文化景区停车场」",
    "parking_info": "南门停车场 ¥5/小时（¥30 封顶），北门地下停车场 ¥6/小时（¥40 封顶）",
}


class ScenicConfig:
    """基于 SQLite 的景区配置存储。"""

    def __init__(self, db_path: str = "data/scenic_config.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._local = threading.local()
        self._init_tables()
        self._seed_defaults()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_tables(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL DEFAULT '',
                label       TEXT NOT NULL DEFAULT '',
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _seed_defaults(self) -> None:
        """首次初始化时写入默认配置。"""
        conn = sqlite3.connect(self._db_path)
        existing = conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]
        if existing == 0:
            labels = {
                "scenic_name": "景区名称",
                "opening_hours": "开放时间",
                "ticket_adult_price": "成人票价",
                "ticket_student_price": "学生票价",
                "ticket_free": "免票政策",
                "address": "景区地址",
                "phone": "客服电话",
                "complaint_phone": "投诉电话",
                "purchase_link": "购票链接",
                "traffic_guide": "交通指南",
                "parking_info": "停车信息",
            }
            for key, value in DEFAULT_CONFIGS.items():
                conn.execute(
                    "INSERT INTO config (key, value, label) VALUES (?, ?, ?)",
                    (key, value, labels.get(key, key)),
                )
            conn.commit()
        conn.close()

    def get(self, key: str) -> Optional[str]:
        """获取单个配置值。"""
        row = self._conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def get_all(self) -> Dict[str, str]:
        """获取所有配置（key→value 字典）。"""
        rows = self._conn.execute("SELECT key, value FROM config").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def get_all_with_labels(self) -> List[Dict[str, Any]]:
        """获取所有配置（含标签），管理后台用。"""
        rows = self._conn.execute(
            "SELECT key, value, label, updated_at FROM config ORDER BY key"
        ).fetchall()
        return [dict(r) for r in rows]

    def set(self, key: str, value: str) -> bool:
        """更新单个配置值。"""
        cursor = self._conn.execute(
            "UPDATE config SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
            (value, key),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def set_batch(self, items: Dict[str, str]) -> int:
        """批量更新配置。返回更新的条目数。"""
        count = 0
        for key, value in items.items():
            if self.set(key, value):
                count += 1
        return count


# 模块级单例
scenic_config = ScenicConfig()
