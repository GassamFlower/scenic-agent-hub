"""
管理后台智能体 — CrewAI 实现。

对应架构图中的 D6（管理后台智能体）。

职责:
- 查询核心运营指标（游客、订单、GMV、退款率）
- 生成运营日报摘要
- 提供异常监控建议（当前为文字建议，后续可接告警系统）
"""

from __future__ import annotations

import logging

from crewai import Agent, Crew, Process, Task

from app.core.config import settings
from app.state import AgentState
from app.tools.crewai_tools import operation_metrics_tool, operation_report_tool

logger = logging.getLogger(__name__)


def _build_admin_agent() -> Agent:
    """构建管理后台 CrewAI Agent。"""
    return Agent(
        role="门神文化景区AI数据分析师",
        goal=(
            "快速、准确地输出运营关键指标和日报摘要，"
            "帮助管理层做决策并识别潜在异常。"
        ),
        backstory=(
            "你是景区运营中心的数据分析负责人，熟悉票务、研学、文创、电商等业务数据口径。"
            "你擅长把复杂指标转化成管理层易读的摘要结论，并给出可执行建议。"
        ),
        tools=[operation_metrics_tool, operation_report_tool],
        llm=settings.crewai_llm,
        verbose=settings.app_env == "dev",
        allow_delegation=False,
        max_iter=8,
        max_execution_time=40,
    )


def run_admin_agent(state: AgentState) -> AgentState:
    """LangGraph 节点函数：调用管理后台智能体。"""
    query = state.get("query", "")
    user_id = state.get("user_id", "guest")
    memory = state.get("memory", [])

    history_text = ""
    if memory:
        history_lines = [f"{m['role']}: {m['content']}" for m in memory[-6:]]
        history_text = "\n\n近期对话记录:\n" + "\n".join(history_lines)

    agent = _build_admin_agent()

    task = Task(
        description=(
            f"你正在服务管理后台用户（用户ID: {user_id}）。\n"
            f"用户请求: 「{query}」\n"
            f"{history_text}\n\n"
            f"请判断需求:\n"
            f"- 如果是看数据指标，调用 query_operation_metrics\n"
            f"- 如果是看日报，调用 generate_operation_report\n"
            f"- 最终给出简洁结论和一条可执行建议"
        ),
        expected_output="管理层可读的运营摘要回复，120字以内",
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
            "agent_type": "admin",
            "crew_output": result.raw,
        }
    except Exception as e:
        logger.error("管理后台智能体执行异常: %s", e, exc_info=True)
        state["final_response"] = "抱歉，运营数据服务暂时繁忙，请稍后重试。"
        state["error"] = str(e)

    return state
