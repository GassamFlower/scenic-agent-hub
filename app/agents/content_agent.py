"""
内容运营智能体 — CrewAI 实现。

对应架构图中的 D2（内容运营智能体）。

职责（来自方案文档）:
- 抖音短视频脚本生成
- 微信公众号长图文创作
- AI 美工设计 Prompt 生成（供 Midjourney / SD 使用）
- 活动策划文案

技术支持:
- 当前: mock 生成模板
- 未来: LLM 直接生成 + OpenClaw 排版 + Coze 自动发布
"""

from __future__ import annotations

import logging

from crewai import Agent, Crew, Process, Task

from app.core.config import settings
from app.state import AgentState
from app.tools.crewai_tools import (
    design_prompt_tool,
    douyin_script_tool,
    wechat_article_tool,
)

logger = logging.getLogger(__name__)


def _build_content_agent() -> Agent:
    """
    构建内容运营 CrewAI Agent。

    角色设定:
    - Role:      门神文化景区 AI 营销部主管
    - Goal:      生成高质量的营销文案和设计素材
    - Backstory: 5年自媒体运营经验，擅长国潮风格内容
    - Tools:     抖音文案、公众号推文、美工 Prompt
    """
    return Agent(
        role="门神文化景区AI营销部主管",
        goal=(
            "根据运营需求生成高质量的营销内容，包括抖音短视频文案、"
            "公众号推文大纲、海报设计提示词等，助力景区全域营销。"
        ),
        backstory=(
            "你是一位有 5 年自媒体运营经验的内容策划专家，"
            "深谙门神文化的历史底蕴，擅长将传统文化与国潮风格融合。"
            "你熟悉抖音、公众号、小红书等平台的内容调性和流量机制。"
            "你创作的内容既有文化深度，又能吸引年轻受众。"
            "根据用户需求选择合适的工具生成内容。"
        ),
        tools=[douyin_script_tool, wechat_article_tool, design_prompt_tool],
        llm=settings.crewai_llm,
        verbose=settings.app_env == "dev",
        allow_delegation=False,
        max_iter=10,
        max_execution_time=60,
    )


def run_content_agent(state: AgentState) -> AgentState:
    """
    LangGraph 节点函数：调用 CrewAI 内容运营智能体。

    与其他 Agent 结构对称:
    AgentState -> CrewAI Crew.kickoff() -> AgentState
    """
    query = state.get("query", "")
    user_id = state.get("user_id", "guest")
    memory = state.get("memory", [])

    history_text = ""
    if memory:
        history_lines = [f"{m['role']}: {m['content']}" for m in memory[-6:]]
        history_text = "\n\n近期对话记录:\n" + "\n".join(history_lines)

    agent = _build_content_agent()

    task = Task(
        description=(
            f"收到一个内容创作需求（来自用户 {user_id}）：\n"
            f"「{query}」\n"
            f"{history_text}\n\n"
            f"请根据需求判断应该使用哪个工具:\n"
            f"- 如果需要抖音文案，使用 generate_douyin_script\n"
            f"- 如果需要公众号文章，使用 generate_wechat_article\n"
            f"- 如果需要设计素材/海报，使用 generate_design_prompt\n"
            f"- 如果不确定，默认生成抖音文案\n"
            f"生成内容后，用简洁中文整理并呈现给用户。"
        ),
        expected_output="生成的营销内容（文案/大纲/设计提示词），格式清晰可用",
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
            "agent_type": "content",
            "crew_output": result.raw,
        }
    except Exception as e:
        logger.error("内容运营智能体执行异常: %s", e, exc_info=True)
        state["final_response"] = "抱歉，内容生成暂时遇到问题，请稍后再试。"
        state["error"] = str(e)

    return state
