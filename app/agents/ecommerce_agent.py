"""
文创电商导购智能体 — CrewAI 实现。

对应架构图中的 D5（文创电商导购智能体）。

职责（来自方案文档）:
- 文创产品推荐与搜索
- 结合门神文化内涵进行商品卖点讲解
- 订单状态查询与物流追踪
- 基础售后回复

技术支持:
- 当前: mock 商品目录 + 模拟订单查询
- 未来: 接电商系统 API + 个性化推荐引擎
"""

from __future__ import annotations

import logging

from crewai import Agent, Crew, Process, Task

from app.core.config import settings
from app.state import AgentState
from app.tools.crewai_tools import product_order_tool, product_search_tool

logger = logging.getLogger(__name__)


def _build_ecommerce_agent() -> Agent:
    """
    构建文创电商 CrewAI Agent。

    角色设定:
    - Role:      门神文化景区金牌导购
    - Goal:      推荐文创商品，处理订单查询
    - Backstory: 熟悉所有文创商品的文化寓意和卖点
    - Tools:     商品搜索、订单查询
    """
    return Agent(
        role="门神文化景区金牌导购",
        goal=(
            "为游客推荐最合适的门神文化文创商品，"
            "结合文化内涵讲解商品卖点，并处理订单状态查询。"
        ),
        backstory=(
            "你是门神文化景区文创商店的金牌导购，对每件商品的文化寓意了如指掌。"
            "你能根据游客的喜好和预算推荐最合适的纪念品。"
            "你熟悉所有门神 IP 周边产品——从冰箱贴到手办到服饰。"
            "推荐时善于讲故事，让顾客觉得买到的不只是商品，更是文化。"
            "查询订单时要准确报出物流信息。"
        ),
        tools=[product_search_tool, product_order_tool],
        llm=settings.crewai_llm,
        verbose=settings.app_env == "dev",
        allow_delegation=False,
        max_iter=10,
        max_execution_time=60,
    )


def run_ecommerce_agent(state: AgentState) -> AgentState:
    """
    LangGraph 节点函数：调用 CrewAI 文创电商导购智能体。
    """
    query = state.get("query", "")
    user_id = state.get("user_id", "guest")
    memory = state.get("memory", [])

    history_text = ""
    if memory:
        history_lines = [f"{m['role']}: {m['content']}" for m in memory[-6:]]
        history_text = "\n\n近期对话记录:\n" + "\n".join(history_lines)

    agent = _build_ecommerce_agent()

    task = Task(
        description=(
            f"你正在接待一位顾客（用户ID: {user_id}）。\n"
            f"顾客说: 「{query}」\n"
            f"{history_text}\n\n"
            f"请根据顾客需求:\n"
            f"- 如果是找商品/纪念品，使用 search_products 工具\n"
            f"- 如果是查订单/物流，使用 query_product_order 工具\n"
            f"- 推荐商品时融入门神文化故事，增强购买吸引力"
        ),
        expected_output="包含商品推荐或订单信息的中文回复，有文化温度，150字以内",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=settings.app_env == "dev",
    )

    try:
        result = crew.kickoff()
        state["final_response"] = result.raw
        state["context"] = {
            **state.get("context", {}),
            "agent_type": "ecommerce",
            "crew_output": result.raw,
        }
    except Exception as e:
        logger.error("电商导购智能体执行异常: %s", e, exc_info=True)
        state["final_response"] = "抱歉，商城系统暂时繁忙，请稍后再试。"
        state["error"] = str(e)

    return state
