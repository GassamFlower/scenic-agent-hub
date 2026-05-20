"""
全渠道智能客服智能体 — CrewAI 实现。

对应架构图中的 D1（全渠道智能客服智能体）。

职责（来自方案文档）:
- 景区的"超级前台"，全平台统一问答出口
- 快速响应开放时间、门票价格、地理位置等常见问题
- 提供景区路线规划，精准回答"草莓园怎么走"等导览问题
- 辅助用户进行简单的查票、核销规则解答
- 意见反馈收集与投诉初步处理

技术支持:
- 当前: FAQ 关键词知识库（api_tools.query_faq）
- 未来: 接入 Dify RAG 向量知识库，提升回答准确率
"""

from __future__ import annotations

import logging

from crewai import Agent, Crew, Process, Task

from app.core.config import settings
from app.state import AgentState
from app.tools.crewai_tools import faq_tool

logger = logging.getLogger(__name__)


def _build_cs_agent() -> Agent:
    """
    构建客服 CrewAI Agent。

    角色设定:
    - Role:      门神文化景区全渠道客服主管
    - Goal:      快速准确回答游客通用问题
    - Backstory: 3年客服经验，熟悉景区每个角落
    - Tools:     景区常见问题查询

    这是流量最大的智能体（预估占 60%），
    回答要求: 准确 > 速度 > 丰富度
    """
    return Agent(
        role="门神文化景区全渠道客服主管",
        goal=(
            "快速、准确地回答游客关于景区的各类通用问题，"
            "包括开放时间、地址交通、门票政策、路线导览、投诉建议等。"
        ),
        backstory=(
            "你是门神文化景区的资深客服，已工作 3 年，熟悉景区每个角落。"
            "你热情友好，回答言简意赅，总能让游客满意。"
            "你必须优先使用知识库工具查询信息，确保回答准确，不编造信息。"
            "遇到超出知识库范围的问题，坦诚告知并建议联系人工客服。"
            "回复要体现门神文化景区的文化特色和服务温度。"
        ),
        tools=[faq_tool],
        llm=settings.crewai_llm,
        verbose=settings.app_env == "dev",
        allow_delegation=False,
        max_iter=8,
        max_execution_time=30,
    )


def run_cs_agent(state: AgentState) -> AgentState:
    """
    LangGraph 节点函数：调用 CrewAI 客服智能体处理通用咨询。
    自动注入景区实时配置（开放时间、票价、购票链接等）。

    与 ticket_agent / study_agent 结构对称:
    AgentState -> CrewAI Crew.kickoff() -> AgentState
    """
    query = state.get("query", "")
    user_id = state.get("user_id", "guest")
    memory = state.get("memory", [])

    # 加载景区实时配置
    from app.core.scenic_config import scenic_config
    config = scenic_config.get_all()

    config_block = "\n".join([
        f"- {key}: {value}"
        for key, value in config.items()
        if key in ("scenic_name", "opening_hours", "ticket_adult_price",
                   "ticket_student_price", "ticket_free", "address",
                   "phone", "purchase_link", "traffic_guide", "parking_info")
    ])

    history_text = ""
    if memory:
        history_lines = [f"{m['role']}: {m['content']}" for m in memory[-6:]]
        history_text = "\n\n近期对话记录:\n" + "\n".join(history_lines)

    agent = _build_cs_agent()

    task = Task(
        description=(
            f"你正在接待一位游客（用户ID: {user_id}）。\n"
            f"游客说: 「{query}」\n"
            f"{history_text}\n\n"
            f"以下是景区当前实时配置，请优先以此为准回答，如配置信息不够再使用 search_faq 工具:\n"
            f"{config_block}\n\n"
            f"如果游客问到购票或价格相关的问题，请在回复末尾附上购票链接: {config.get('purchase_link', '可前往景区小程序购票')}\n"
            f"请用友好、简洁的中文回复游客。"
        ),
        expected_output="基于景区配置和知识库的准确中文回复，简洁友好，必要时附购票链接",
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
            "agent_type": "customer_service",
            "crew_output": result.raw,
        }
    except Exception as e:
        logger.error("客服智能体执行异常: %s", e, exc_info=True)
        state["final_response"] = "抱歉，系统暂时繁忙，请稍后再试或拨打人工客服热线 0371-12345678。"
        state["error"] = str(e)

    return state
