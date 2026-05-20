"""
LangGraph 工作流定义。

本文件是整个系统的"交通中枢"，负责:
1. 定义所有节点（登录拦截、意图分类、6 类业务智能体、审核、收尾）
2. 定义路由规则（条件边）
3. 编译为可执行的 StateGraph

主链路:
  START -> login_guard
    -> (已登录) classify_intent -> ticket/study/cs/content/ecommerce/admin/unknown
    -> 业务节点 -> hitl_gate -> (需审核? finalize : END)
    -> (未登录) finalize -> END
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.agents.admin_agent import run_admin_agent
from app.agents.content_agent import run_content_agent
from app.agents.cs_agent import run_cs_agent
from app.agents.ecommerce_agent import run_ecommerce_agent
from app.agents.study_agent import run_study_agent
from app.agents.ticket_agent import run_ticket_agent
from app.core.config import settings
from app.core.review import review_queue
from app.state import AgentState, Intent

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#  意图分类 — LLM 版（含关键词降级兜底）
# ════════════════════════════════════════════════════════════

INTENT_SYSTEM_PROMPT = """你是一个意图分类器。根据用户的输入，判断意图属于以下哪个类别：

- ticket: 票务相关（买票、查票、订单、退票、改签、门票价格、余票）
- study: 研学相关（研学课程、学习活动、带孩子参观、教育体验、文化讲解预约）
- customer_service: 通用客服（开放时间、怎么去、地址、停车、路线指引、投诉、建议、一票多用规则）
- content: 内容运营（写文案、抖音脚本、公众号文章、海报设计、营销推广、宣传素材）
- ecommerce: 文创电商（买纪念品、文创商品、手办、周边产品、查物流、查商品订单）
- admin: 管理后台（运营数据、日报、异常监控、报表分析）
- unknown: 以上都不匹配

规则：
1. 只回复一个英文单词：ticket、study、customer_service、content、ecommerce、admin 或 unknown
2. 不要输出任何解释或标点
3. 如果用户的问题同时涉及多个类别，选择最主要的那个"""

VALID_INTENTS = (
    "ticket",
    "study",
    "customer_service",
    "content",
    "ecommerce",
    "admin",
)


def _llm_classify(query: str) -> Intent:
    """调用 LLM 做意图分类（通过 litellm，支持 DeepSeek/Qwen/OpenAI）。"""
    import litellm

    response = litellm.completion(
        model=settings.crewai_llm,
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0,
        max_tokens=20,
    )
    raw = response.choices[0].message.content.strip().lower()

    for intent in VALID_INTENTS:
        if intent in raw:
            return intent  # type: ignore[return-value]
    return "unknown"


def _keyword_classify(query: str) -> Intent:
    """关键词兜底分类（LLM 不可用时降级使用）。"""
    if any(k in query for k in ["票", "车次", "订单", "出行", "退票", "改签", "门票"]):
        return "ticket"
    if any(k in query for k in ["研学", "课程", "学习", "学校", "带孩子"]):
        return "study"
    if any(k in query for k in ["时间", "地址", "怎么去", "停车", "投诉", "客服", "几点"]):
        return "customer_service"
    if any(k in query for k in ["文案", "抖音", "公众号", "推文", "海报", "营销", "宣传"]):
        return "content"
    if any(k in query for k in ["文创", "商品", "纪念品", "购物", "手办", "快递", "物流"]):
        return "ecommerce"
    if any(k in query for k in ["运营", "报表", "日报", "数据看板", "gmv", "退款率", "统计"]):
        return "admin"
    return "unknown"


# ════════════════════════════════════════════════════════════
#  LangGraph 节点函数
# ════════════════════════════════════════════════════════════


def login_guard(state: AgentState) -> AgentState:
    """登录拦截节点：未登录时直接写入提示，由路由进入 finalize。"""
    if not state.get("authenticated", False):
        state["final_response"] = "请先登录后再继续操作。"
    return state


def classify_intent(state: AgentState) -> AgentState:
    """
    意图识别节点 — LLM 优先，关键词兜底。

    策略:
    1. 优先调用 LLM 做分类（准确率高，支持模糊语义）
    2. 如果 LLM 调用失败（Key 未配、网络超时等），降级为关键词匹配
    3. 无论哪种方式，结果都写入 state["intent"]
    """
    query = state.get("query", "")
    try:
        intent = _llm_classify(query)
        logger.info("LLM 意图分类结果: %s (query=%s)", intent, query[:50])
    except Exception as e:
        logger.warning("LLM 意图分类失败，降级为关键词匹配: %s", e)
        intent = _keyword_classify(query)
        logger.info("关键词意图分类结果: %s (query=%s)", intent, query[:50])
    state["intent"] = intent
    return state


def unknown_handler(state: AgentState) -> AgentState:
    """兜底节点：意图不明时返回引导语。"""
    state["final_response"] = (
        "暂未识别您的意图。您可以试试：\n"
        "- 查询门票/订单（票务）\n"
        "- 了解研学课程（研学）\n"
        "- 咨询开放时间、地址等（客服）\n"
        "- 生成营销文案（内容运营）\n"
        "- 选购文创纪念品（电商）\n"
        "- 查看运营数据与日报（管理后台）"
    )
    return state


def hitl_gate(state: AgentState) -> AgentState:
    """
    Human-in-the-loop 网关。

    当 require_human_review=True 时:
    1. 将当前请求和 Agent 回复提交到审核队列
    2. 返回审核单号，告知用户等待
    3. 运营人员通过 /api/v1/reviews 接口处理审核
    """
    if state.get("require_human_review"):
        review_id = review_queue.submit(
            session_id=state.get("session_id", ""),
            user_id=state.get("user_id", ""),
            query=state.get("query", ""),
            agent_response=state.get("final_response", ""),
            intent=state.get("intent", "unknown"),
        )
        state["review_id"] = review_id
        state["final_response"] = (
            f"该请求已提交人工审核（审核单号: {review_id}），"
            f"请稍后查看结果。"
        )
    return state


def finalize(state: AgentState) -> AgentState:
    """统一收尾节点：回写对话记忆。"""
    memory = state.get("memory", [])
    memory.append({"role": "user", "content": state.get("query", "")})
    memory.append({"role": "assistant", "content": state.get("final_response", "")})
    state["memory"] = memory
    return state


# ════════════════════════════════════════════════════════════
#  路由函数
# ════════════════════════════════════════════════════════════


def _route_auth(state: AgentState) -> str:
    """登录路由：已登录 -> classify_intent，未登录 -> finalize。"""
    return "classify_intent" if state.get("authenticated", False) else "finalize"


def _route_intent(state: AgentState) -> str:
    """意图路由：根据 intent 分发到对应业务节点。"""
    return state.get("intent", "unknown")


def _route_hitl(state: AgentState) -> str:
    """审核路由：需要人工审核则走 finalize，否则直接 END。"""
    return "finalize" if state.get("require_human_review") else "end"


# ════════════════════════════════════════════════════════════
#  构建并编译 StateGraph
# ════════════════════════════════════════════════════════════


def build_graph():
    """
    构建 LangGraph 工作流。

    节点清单（共 11 个）:
      login_guard, classify_intent,
      ticket_agent, study_agent, cs_agent, content_agent, ecommerce_agent, admin_agent,
      unknown_handler, hitl_gate, finalize
    """
    graph = StateGraph(AgentState)

    # ── 注册节点 ──
    graph.add_node("login_guard", login_guard)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("ticket_agent", run_ticket_agent)
    graph.add_node("study_agent", run_study_agent)
    graph.add_node("cs_agent", run_cs_agent)
    graph.add_node("content_agent", run_content_agent)
    graph.add_node("ecommerce_agent", run_ecommerce_agent)
    graph.add_node("admin_agent", run_admin_agent)
    graph.add_node("unknown_handler", unknown_handler)
    graph.add_node("hitl_gate", hitl_gate)
    graph.add_node("finalize", finalize)

    # ── 连接边 ──
    graph.add_edge(START, "login_guard")

    graph.add_conditional_edges(
        "login_guard",
        _route_auth,
        {"classify_intent": "classify_intent", "finalize": "finalize"},
    )

    graph.add_conditional_edges(
        "classify_intent",
        _route_intent,
        {
            "ticket": "ticket_agent",
            "study": "study_agent",
            "customer_service": "cs_agent",
            "content": "content_agent",
            "ecommerce": "ecommerce_agent",
            "admin": "admin_agent",
            "unknown": "unknown_handler",
        },
    )

    graph.add_edge("ticket_agent", "hitl_gate")
    graph.add_edge("study_agent", "hitl_gate")
    graph.add_edge("cs_agent", "hitl_gate")
    graph.add_edge("content_agent", "hitl_gate")
    graph.add_edge("ecommerce_agent", "hitl_gate")
    graph.add_edge("admin_agent", "hitl_gate")
    graph.add_edge("unknown_handler", "finalize")

    graph.add_conditional_edges(
        "hitl_gate", _route_hitl, {"finalize": "finalize", "end": END}
    )
    graph.add_edge("finalize", END)

    return graph.compile()


# 模块级单例图对象，在 FastAPI 启动时即可复用
app_graph = build_graph()
