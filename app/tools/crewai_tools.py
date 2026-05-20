"""
CrewAI @tool 包装层。

设计思路：
- api_tools.py 保留"原始实现"（纯函数，方便单元测试、直接调用）
- 本文件将原始函数封装为 CrewAI Agent 可理解和调用的 Tool
- @tool 装饰器会把函数签名和 docstring 暴露给 LLM，
  LLM 根据描述决定何时调用、传什么参数

注意：
- @tool 名称必须是合法英文标识符（字母/数字/下划线），不能用中文
- docstring 的质量直接影响 Agent 是否能正确调用工具
- 返回值建议是自然语言文本，便于 Agent 整合到最终回复中
"""

from __future__ import annotations

from crewai.tools import tool

from app.tools.api_tools import (
    create_ticket_order,
    generate_design_prompt,
    generate_douyin_script,
    generate_operation_report,
    generate_wechat_article,
    query_faq,
    query_operation_metrics,
    query_product_order,
    query_study_plan,
    query_ticket_inventory,
    search_products,
)


# ── 票务相关工具 ────────────────────────────────────────────


@tool("query_ticket_inventory")
def ticket_inventory_tool(route: str, date: str) -> str:
    """查询指定线路和日期的门票库存与价格。当游客询问票价、余票、是否有票时使用。

    Args:
        route: 线路名称，例如 "北京-上海" 或 "上海-杭州"
        date: 出行日期，格式 YYYY-MM-DD，例如 "2026-04-01"
    """
    result = query_ticket_inventory(route=route, date=date)
    return (
        f"线路: {result['route']}，日期: {result['date']}，"
        f"余票: {result['available']} 张，"
        f"票价: {result['price']} {result['currency']}"
    )


@tool("create_ticket_order")
def ticket_order_tool(user_id: str, route: str, date: str) -> str:
    """为游客创建票务订单。仅在游客明确表示要购票/下单时才调用。

    Args:
        user_id: 用户唯一标识
        route: 购票线路
        date: 出行日期，格式 YYYY-MM-DD
    """
    result = create_ticket_order(user_id=user_id, route=route, date=date)
    return (
        f"订单创建成功！订单号: {result['order_id']}，"
        f"线路: {result['route']}，日期: {result['date']}，"
        f"状态: {result['status']}"
    )


# ── 研学相关工具 ────────────────────────────────────────────


@tool("query_study_plan")
def study_plan_tool(city: str, days: int) -> str:
    """根据目标城市和天数查询可用的研学课程方案。

    Args:
        city: 目标城市名称，例如 "北京" 或 "上海"
        days: 研学天数，整数
    """
    result = query_study_plan(city=city, days=days)
    return (
        f"城市: {result['city']}，天数: {result['days']} 天，"
        f"主题: {result['theme']}，"
        f"适合学段: {result['recommended_school_level']}"
    )


# ── 客服相关工具 ────────────────────────────────────────────


@tool("search_faq")
def faq_tool(keyword: str) -> str:
    """检索景区常见问题知识库。当游客询问开放时间、地址、停车、退改签规则等通用问题时使用。

    Args:
        keyword: 查询关键词，例如 "开放时间"、"停车"、"退改签"
    """
    return query_faq(keyword=keyword)


# ── 内容运营相关工具（D2）────────────────────────────────────


@tool("generate_douyin_script")
def douyin_script_tool(topic: str, style: str = "国潮") -> str:
    """根据主题和风格生成抖音短视频文案脚本。用于营销内容创作。

    Args:
        topic: 视频主题，例如 "秦叔宝的故事" 或 "门神文化探秘"
        style: 内容风格，例如 "国潮"、"搞笑"、"知识科普"，默认 "国潮"
    """
    result = generate_douyin_script(topic=topic, style=style)
    return (
        f"平台: {result['platform']}，时长: {result['duration']}\n"
        f"脚本:\n{result['script']}\n"
        f"推荐标签: {result['hashtags']}"
    )


@tool("generate_wechat_article")
def wechat_article_tool(topic: str, length: str = "中篇") -> str:
    """根据主题生成微信公众号推文大纲和草稿。用于长图文内容创作。

    Args:
        topic: 文章主题，例如 "门神年画" 或 "春节门神习俗"
        length: 文章长度，"短篇"约800字、"中篇"约1500字，默认 "中篇"
    """
    result = generate_wechat_article(topic=topic, length=length)
    return (
        f"标题: {result['title']}\n"
        f"预估字数: {result['word_count_estimate']}\n"
        f"大纲:\n{result['outline']}"
    )


@tool("generate_design_prompt")
def design_prompt_tool(theme: str) -> str:
    """生成适用于AI绘图工具（Midjourney等）的设计提示词。用于海报/宣传物料设计。

    Args:
        theme: 设计主题或风格，例如 "新年门神" 或 "Q版秦叔宝"
    """
    result = generate_design_prompt(theme=theme)
    return (
        f"主题: {result['theme']}\n"
        f"Prompt: {result['prompt']}\n"
        f"Negative: {result['negative_prompt']}\n"
        f"推荐工具: {result['recommended_tool']}"
    )


# ── 文创电商相关工具（D5）────────────────────────────────────


@tool("search_products")
def product_search_tool(keyword: str) -> str:
    """在文创商城中搜索商品。当游客询问纪念品、周边、文创产品时使用。

    Args:
        keyword: 搜索关键词，例如 "冰箱贴"、"手办"、"T恤"、"文创"
    """
    return search_products(keyword=keyword)


@tool("query_product_order")
def product_order_tool(order_id: str) -> str:
    """查询文创商品订单的物流和配送状态。

    Args:
        order_id: 订单编号
    """
    result = query_product_order(order_id=order_id)
    return (
        f"订单号: {result['order_id']}，状态: {result['status']}，"
        f"物流: {result['logistics']}，{result['estimated_delivery']}"
    )


# ── 管理后台相关工具（D6）────────────────────────────────────


@tool("query_operation_metrics")
def operation_metrics_tool(period: str = "today") -> str:
    """查询景区运营核心指标（游客量、订单量、GMV、退款率）。

    Args:
        period: 统计周期，可选 today/yesterday/week/month
    """
    m = query_operation_metrics(period=period)
    return (
        f"{m['period']}数据：游客 {m['visitors']} 人次，"
        f"门票订单 {m['ticket_orders']} 单，研学订单 {m['study_orders']} 单，"
        f"GMV {m['gmv']} 元，退款率 {m['refund_rate']}。"
    )


@tool("generate_operation_report")
def operation_report_tool(period: str = "today") -> str:
    """生成运营日报摘要文本，便于管理层快速查看。

    Args:
        period: 统计周期，可选 today/yesterday/week/month
    """
    return generate_operation_report(period=period)
