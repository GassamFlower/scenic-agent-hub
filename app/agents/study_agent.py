"""
研学智能体 — CrewAI 实现。

对应架构图中的 D3（研学接待智能体）。

职责（来自方案文档）:
- 门神文化互动式讲解
- 研学课程推荐与预约管理
- 定制化欢迎词和带队讲解稿生成
- 学生/家长反馈收集

在 LangGraph 工作流中作为一个节点被调用：
    graph.add_node("study_agent", run_study_agent)

执行流程与 ticket_agent 对称：
    AgentState -> CrewAI Crew.kickoff() -> AgentState
"""

from __future__ import annotations

import logging

from crewai import Agent, Crew, Process, Task

from app.core.config import settings
from app.state import AgentState
from app.tools.crewai_tools import study_plan_tool

logger = logging.getLogger(__name__)


def _build_study_agent() -> Agent:
    """
    构建研学 CrewAI Agent。

    角色设定:
    - Role:      门神文化景区金牌研学讲师
    - Goal:      推荐合适的研学课程，讲解门神文化
    - Backstory: 教育学背景，擅长互动式教学
    - Tools:     查询研学方案
    """
    return Agent(
        role="门神文化景区金牌研学讲师",
        goal=(
            "为不同年龄段的学生和家长推荐最合适的研学课程，"
            "并用生动有趣的方式讲解门神文化的历史渊源。"
        ),
        backstory=(
            "你是一位有教育学背景的文化讲解员，在门神文化景区担任研学项目负责人。"
            "你擅长根据学生年龄段调整讲解难度，让小学生觉得有趣，让中学生有收获。"
            "你熟悉所有研学课程的内容、时长、适合年龄和预约流程。"
            "回答时要热情、专业，善于用小故事引入门神文化知识。"
        ),
        tools=[study_plan_tool],
        llm=settings.crewai_llm,
        verbose=settings.app_env == "dev",
        allow_delegation=False,
        max_iter=10,
        max_execution_time=60,
    )


def run_study_agent(state: AgentState) -> AgentState:
    """
    LangGraph 节点函数：调用 CrewAI 研学智能体处理用户请求。

    与 ticket_agent 的 run_ticket_agent 结构对称：
    - 提取 state 中的 query + memory
    - 构建 Task 描述
    - Crew.kickoff() 执行
    - 结果回写 state
    """
    query = state.get("query", "")
    user_id = state.get("user_id", "guest")
    memory = state.get("memory", [])

    history_text = ""
    if memory:
        history_lines = [f"{m['role']}: {m['content']}" for m in memory[-6:]]
        history_text = "\n\n近期对话记录:\n" + "\n".join(history_lines)

    agent = _build_study_agent()

    task = Task(
        description=(
            f"你正在接待一位访客（用户ID: {user_id}）。\n"
            f"访客说: 「{query}」\n"
            f"{history_text}\n\n"
            f"请根据访客需求完成以下工作:\n"
            f"1. 调用 query_study_plan 工具获取课程建议\n"
            f"2. 结合门神文化特色，给出个性化推荐\n"
            f"3. 如果访客提到孩子年龄，据此推荐适合学段的课程"
        ),
        expected_output="包含研学方案推荐的中文回复，生动友好，150字以内",
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
            "agent_type": "study",
            "crew_output": result.raw,
        }
    except Exception as e:
        logger.error("研学智能体执行异常: %s", e, exc_info=True)
        state["final_response"] = "抱歉，研学系统暂时繁忙，请稍后再试或联系人工客服。"
        state["error"] = str(e)

    return state
