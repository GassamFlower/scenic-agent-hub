"""
景区知识库管理模块（FAQ 持久化）。

用于管理后台对景区常见问题进行增删改查。
CrewAI 的 cs_agent（客服智能体）通过 api_tools.query_faq() 读取此库。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class KnowledgeBase:
    """基于 SQLite 的知识库存储。"""

    def __init__(self, db_path: str = "data/knowledge.db"):
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
            CREATE TABLE IF NOT EXISTS faq (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                keywords    TEXT NOT NULL,           -- 逗号分隔，用于 LLM 匹配
                question    TEXT NOT NULL,           -- 常见问题表述
                answer      TEXT NOT NULL,           -- 标准回答
                category    TEXT NOT NULL DEFAULT '通用',
                enabled     INTEGER NOT NULL DEFAULT 1,
                hit_count   INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _seed_defaults(self) -> None:
        """首次初始化时写入景区默认知识库条目。"""
        conn = sqlite3.connect(self._db_path)
        count = conn.execute("SELECT COUNT(*) FROM faq").fetchone()[0]
        if count == 0:
            defaults = [
                ("开放时间,营业时间", "景区开放时间是什么？",
                 "门神文化景区每日开放时间为 08:30 - 17:30（夏季延长至 18:00），全年无休（除夕闭馆）。", "票务"),
                ("门票,价格,票价", "门票多少钱一张？",
                 "成人票 ¥68/张，学生票 ¥38/张（需持学生证），60岁以上老人免票（需持身份证）。", "票务"),
                ("地址,怎么去,交通", "景区地址和交通方式？",
                 "地址：湖北省武汉市黄陂区门神文化大道 1 号。\n交通：地铁 2 号线至「门神站」A 口出站步行 5 分钟即到；自驾导航搜索「门神文化景区停车场」。", "交通"),
                ("停车场,停车", "景区有停车场吗？",
                 "景区设有两个停车场：\n1. 南门停车场（地面，500 车位）¥5/小时，¥30 封顶\n2. 北门地下停车场（800 车位）¥6/小时，¥40 封顶", "交通"),
                ("研学,课程,活动", "可以带孩子来研学吗？有什么课程？",
                 "景区设有「小小门神」研学项目，包含：\n- 门神年画拓印体验（¥68/人，约 1 小时）\n- 秦叔宝故事讲解（¥48/人，约 40 分钟）\n- 门神主题手工课（¥88/人，约 1.5 小时）\n适合 5-15 岁儿童，需提前 1 天预约。", "研学"),
                ("讲解,讲解员,导游", "有讲解服务吗？",
                 "景区提供三种讲解服务：\n1. 人工讲解：¥100/团（10 人内，需预约）\n2. 语音导览器：¥20/台（押金 ¥100）\n3. 微信小程序免费语音导览", "服务"),
                ("退票,改签,取消", "门票可以退吗？",
                 "未使用的电子票可于游玩日前一天 24:00 前免费退票；游玩当日退票收取 20% 手续费；过期作废不退。", "票务"),
                ("餐饮,吃饭,餐厅", "景区里有吃饭的地方吗？",
                 "景区内设有一家主题餐厅「门神食坊」（人均 ¥60）、一家咖啡馆「尉迟拿铁」（人均 ¥30），南门外有美食街。", "服务"),
                ("客服,电话,联系", "怎么联系人工客服？",
                 "客服热线：027-12345678（09:00-18:00）\n在线客服：微信公众号「门神文化景区」- 在线咨询", "服务"),
                ("WiFi,网络,上网", "景区有 WiFi 吗？",
                 "景区全区域覆盖免费 WiFi，SSID：Menshen_Free，无需密码即可连接。", "服务"),
                ("一票多用,优惠,折扣", "门票还有什么额外优惠？",
                 "持门票在景区内合作商户消费可享以下优惠：\n- 门神食坊 9 折\n- 尉迟拿铁 8.5 折\n- 文创店满 ¥100 减 ¥10\n详情请在消费时出示门票二维码。", "票务"),
                ("拍照,摄影,摄像", "景区可以拍照吗？",
                 "景区内允许个人拍照和录像，但禁止使用闪光灯（文物保护区）。商业拍摄需提前申请。", "服务"),
                ("卫生间,厕所,母婴室", "景区有卫生间和母婴室吗？",
                 "景区设有 5 处公共卫生间（分布图可在小程序查看），其中 2 处配有母婴室和无障碍设施。", "服务"),
                ("宠物,狗,猫", "可以带宠物入园吗？",
                 "为了文物安全和游客体验，景区禁止携带宠物入园。导盲犬除外（需出示相关证明）。", "服务"),
                ("纪念品,文创,商店", "文创商店在哪里？",
                 "文创商店位于游客中心出口处，售卖门神主题冰箱贴、明信片、手办、T 恤等纪念品。支持微信/支付宝。", "文创"),
            ]
            conn.executemany(
                "INSERT INTO faq (keywords, question, answer, category) VALUES (?, ?, ?, ?)",
                defaults,
            )
            conn.commit()
        conn.close()

    # ── 查询 ────────────────────────────────────────────────

    def search(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """按关键词搜索启用的知识库条目（供 LLM Agent 使用）。"""
        like = f"%{keyword}%"
        rows = self._conn.execute(
            "SELECT * FROM faq WHERE enabled = 1 AND (keywords LIKE ? OR question LIKE ? OR answer LIKE ?) LIMIT ?",
            (like, like, like, limit),
        ).fetchall()
        results = [dict(r) for r in rows]
        # 增加命中计数
        for r in results:
            self._conn.execute("UPDATE faq SET hit_count = hit_count + 1 WHERE id = ?", (r["id"],))
        self._conn.commit()
        return results

    def get_by_id(self, faq_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("SELECT * FROM faq WHERE id = ?", (faq_id,)).fetchone()
        return dict(row) if row else None

    def list_all(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        if enabled_only:
            rows = self._conn.execute(
                "SELECT * FROM faq WHERE enabled = 1 ORDER BY hit_count DESC, id ASC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM faq ORDER BY hit_count DESC, id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── 增删改 ──────────────────────────────────────────────

    def add(self, keywords: str, question: str, answer: str, category: str = "通用") -> int:
        cursor = self._conn.execute(
            "INSERT INTO faq (keywords, question, answer, category) VALUES (?, ?, ?, ?)",
            (keywords, question, answer, category),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update(self, faq_id: int, **kwargs) -> bool:
        allowed = {"keywords", "question", "answer", "category", "enabled"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = "datetime('now')"
        set_clause = ", ".join(f"{k} = ?" if k != "updated_at" else f"{k} = datetime('now')" for k in updates)
        values = [v for k, v in updates.items() if k != "updated_at"]
        values.append(faq_id)
        cursor = self._conn.execute(f"UPDATE faq SET {set_clause} WHERE id = ?", values)
        self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, faq_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM faq WHERE id = ?", (faq_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_categories(self) -> List[str]:
        rows = self._conn.execute("SELECT DISTINCT category FROM faq ORDER BY category").fetchall()
        return [r["category"] for r in rows]


# 模块级单例
knowledge_base = KnowledgeBase()
