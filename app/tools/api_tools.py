"""
原始工具函数层 — 纯 Python 实现，无 AI 依赖。

设计原则:
- 每个函数都是可直接调用、可单元测试的纯函数
- 当前为 mock 实现，未来逐个替换为真实 API/SDK 调用
- crewai_tools.py 中的 @tool 装饰器会包装这些函数供 Agent 使用
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4


# ════════════════════════════════════════════════════════════
#  票务相关
# ════════════════════════════════════════════════════════════


def query_ticket_inventory(route: str, date: str) -> Dict[str, str]:
    """
    模拟票务库存查询。

    未来替换: 接真实票务服务 SDK/HTTP API + 异常处理 + 重试
    """
    return {
        "route": route,
        "date": date,
        "available": "42",
        "price": "299",
        "currency": "CNY",
    }


def create_ticket_order(user_id: str, route: str, date: str) -> Dict[str, str]:
    """模拟下单接口，返回最小订单结构。"""
    return {
        "order_id": f"TKT-{uuid4().hex[:10].upper()}",
        "user_id": user_id,
        "route": route,
        "date": date,
        "created_at": datetime.utcnow().isoformat(),
        "status": "created",
    }


# ════════════════════════════════════════════════════════════
#  研学相关
# ════════════════════════════════════════════════════════════


def query_study_plan(city: str, days: int) -> Dict[str, str]:
    """模拟研学方案查询。"""
    return {
        "city": city,
        "days": str(days),
        "theme": "科技+人文研学",
        "recommended_school_level": "小学高年级-初中",
    }


# ════════════════════════════════════════════════════════════
#  客服 FAQ 知识库
# ════════════════════════════════════════════════════════════


def query_faq(keyword: str) -> str:
    """
    景区知识库检索 — 从持久化 KnowledgeBase 中查询。

    未来替换: 接入 Dify RAG 向量知识库做语义检索（保留 keywords 精确匹配兜底）
    """
    from app.core.knowledge_base import knowledge_base

    keyword = keyword.strip()
    results = knowledge_base.search(keyword, limit=5)

    if not results:
        # 记录未命中问题
        from app.core.unanswered import unanswered_tracker
        unanswered_tracker.record(query=keyword, intent="customer_service")
        return f"未找到与「{keyword}」相关的信息，建议联系人工客服获取帮助。"

    lines = []
    for r in results:
        lines.append(f"【{r['question']}】{r['answer']}")
    return "\n\n".join(lines)


# ════════════════════════════════════════════════════════════
#  内容运营相关（D2）
# ════════════════════════════════════════════════════════════


def generate_douyin_script(topic: str, style: str = "国潮") -> Dict[str, str]:
    """
    模拟生成抖音短视频文案脚本。

    未来替换: LLM 直接生成 + 热点 API 融合
    """
    return {
        "platform": "抖音",
        "topic": topic,
        "style": style,
        "duration": "30s",
        "script": (
            f"【开头-3s】近景特写门神浮雕，配乐《醉太平》节奏点\n"
            f"【中段-20s】以「{topic}」为主线，讲述门神文化故事，"
            f"风格偏{style}，节奏轻快\n"
            f"【结尾-7s】'关注我，带你走进千年门神文化' + 景区定位标签"
        ),
        "hashtags": "#门神文化 #国潮探店 #开封旅游",
    }


def generate_wechat_article(topic: str, length: str = "中篇") -> Dict[str, str]:
    """
    模拟生成公众号推文草稿。

    未来替换: LLM 长文生成 + 排版模板引擎
    """
    return {
        "platform": "微信公众号",
        "topic": topic,
        "length": length,
        "title": f"走进门神文化：{topic}的前世今生",
        "outline": (
            f"一、{topic}的历史渊源\n"
            f"二、门神文化景区中的{topic}元素\n"
            f"三、打卡攻略与推荐路线\n"
            f"四、文创周边推荐"
        ),
        "word_count_estimate": "1500" if length == "中篇" else "800",
    }


def generate_design_prompt(theme: str) -> Dict[str, str]:
    """
    模拟生成美工设计 Prompt（供 Midjourney / SD 使用）。

    未来替换: 基于风格库自动匹配 + 多尺寸适配
    """
    return {
        "theme": theme,
        "prompt": (
            f"A Chinese traditional door god illustration in {theme} style, "
            f"vibrant colors, intricate details, featuring Qin Shubao and "
            f"Yuchi Gong, modern flat design with cultural elements, "
            f"8k resolution --ar 9:16 --style raw"
        ),
        "negative_prompt": "low quality, blurry, western style",
        "recommended_tool": "Midjourney v6",
    }


# ════════════════════════════════════════════════════════════
#  文创电商相关（D5）
# ════════════════════════════════════════════════════════════


PRODUCT_CATALOG: List[Dict[str, Any]] = [
    {"id": "P001", "name": "门神文创冰箱贴", "price": 29, "stock": 120, "category": "文创"},
    {"id": "P002", "name": "秦叔宝Q版手办", "price": 199, "stock": 50, "category": "手办"},
    {"id": "P003", "name": "尉迟恭钥匙扣", "price": 39, "stock": 200, "category": "文创"},
    {"id": "P004", "name": "门神文化帆布包", "price": 89, "stock": 80, "category": "服饰"},
    {"id": "P005", "name": "国潮门神T恤", "price": 149, "stock": 60, "category": "服饰"},
    {"id": "P006", "name": "门神文化笔记本套装", "price": 59, "stock": 150, "category": "文具"},
    {"id": "P007", "name": "门神守护挂饰（车载）", "price": 79, "stock": 90, "category": "饰品"},
]


def search_products(keyword: str) -> str:
    """
    模拟文创商品搜索。

    未来替换: 接电商系统商品搜索 API + 个性化推荐引擎
    """
    matches = [
        p for p in PRODUCT_CATALOG
        if keyword in p["name"] or keyword in p["category"]
    ]
    if not matches:
        return f"未找到与「{keyword}」相关的商品。"
    lines = []
    for p in matches:
        lines.append(
            f"[{p['id']}] {p['name']} — ¥{p['price']} "
            f"（库存 {p['stock']}）"
        )
    return "\n".join(lines)


def query_product_order(order_id: str) -> Dict[str, str]:
    """
    模拟文创订单状态查询。

    未来替换: 接电商系统订单 API
    """
    return {
        "order_id": order_id,
        "status": "已发货",
        "logistics": "顺丰速运 SF1234567890",
        "estimated_delivery": "预计 2-3 个工作日送达",
    }


# ════════════════════════════════════════════════════════════
#  管理后台相关（D6）
# ════════════════════════════════════════════════════════════


def query_operation_metrics(period: str = "today") -> Dict[str, str]:
    """
    模拟运营指标查询。

    未来替换: 接 BI/数据仓库 API（如 ClickHouse、PostgreSQL 报表库）
    """
    # 简化 mock：不同周期返回不同文案
    period_map = {
        "today": "今日",
        "yesterday": "昨日",
        "week": "近7日",
        "month": "近30日",
    }
    title = period_map.get(period, "今日")
    return {
        "period": title,
        "visitors": "12876",
        "ticket_orders": "3241",
        "study_orders": "286",
        "gmv": "562340",
        "refund_rate": "1.8%",
    }


def generate_operation_report(period: str = "today") -> str:
    """
    模拟生成运营日报。

    未来替换: 自动聚合多数据源并生成结构化日报（markdown/pdf）
    """
    m = query_operation_metrics(period)
    return (
        f"{m['period']}运营简报：游客 {m['visitors']} 人次，"
        f"门票订单 {m['ticket_orders']} 单，研学订单 {m['study_orders']} 单，"
        f"GMV {m['gmv']} 元，退款率 {m['refund_rate']}。"
    )
