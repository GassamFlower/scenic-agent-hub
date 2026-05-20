"""
LangGraph 工作流共享状态定义。

AgentState 是所有节点之间流转的"上下文载体"，
类似工作流的"内存总线"——每个节点只读写自己关心的键。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


# 当前项目支持的意图类型（共 6 类业务 + 1 兜底）:
# - ticket:           票务相关（查票、下单、退改签、价格）
# - study:            研学相关（课程推荐、文化讲解、预约）
# - customer_service: 通用客服（开放时间、地址、路线、投诉建议）
# - content:          内容运营（抖音文案、公众号推文、海报设计）
# - ecommerce:        文创电商（商品推荐、订单查询、纪念品导购）
# - admin:            运营管理（数据统计、日报、异常监控）
# - unknown:          暂未识别
Intent = Literal[
    "ticket",
    "study",
    "customer_service",
    "content",
    "ecommerce",
    "admin",
    "unknown",
]


class AgentState(TypedDict, total=False):
    """
    LangGraph 在节点间流转的共享状态对象。

    设计原则:
    - total=False: 允许节点按需写入字段，不要求一次性填满
    - 所有节点只"增量修改"自己关心的键，降低耦合
    """

    # 会话标识（用于多轮对话持久化）
    session_id: str
    # 当前用户标识，可用于鉴权、订单归属、画像等
    user_id: str
    # 登录态（登录拦截节点会读取）
    authenticated: bool
    # 用户输入原文
    query: str
    # 意图识别结果（由 classify_intent 写入）
    intent: Intent
    # 对话记忆（由 SessionStore 持久化管理）
    memory: List[Dict[str, str]]
    # 是否需要人工审核（Human-in-the-loop）
    require_human_review: bool
    # 人工审核单号（由 hitl_gate 写入）
    review_id: Optional[str]
    # 最终返回给前端/调用方的文本
    final_response: str
    # 各业务节点产出的结构化数据（库存、订单、研学方案等）
    context: Dict[str, Any]
    # 透传元信息（如请求来源、小程序 session 信息等）
    metadata: Dict[str, Any]
    # 错误信息占位
    error: Optional[str]
