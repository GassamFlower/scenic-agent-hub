"""
票务智能体 — CrewAI 实现。

对应架构图中的 D4（票务 & 商户联盟智能体）。

职责（来自方案文档）:
- 门票查询与购买引导
- 优惠活动推送
- "一票多用"联盟规则解释
- 订单管理与退改签服务

在 LangGraph 工作流中作为一个节点被调用：
    graph.add_node("ticket_agent", run_ticket_agent)

执行流程:
    1. 从 AgentState 中提取 query、user_id、历史对话
    2. 构建 CrewAI Task（把用户问题 + 上下文传给 Agent）
    3. Agent 自主决定是否调用工具（查库存/下单）
    4. 将 Agent 的自然语言回复写回 state["final_response"]
    5. 将结构化数据写回 state["context"]
"""

from __future__ import annotations

import logging

from crewai import Agent, Crew, Process, Task

from app.core.config import settings
from app.state import AgentState
from app.tools.crewai_tools import ticket_inventory_tool, ticket_order_tool

logger = logging.getLogger(__name__)


def _build_ticket_agent() -> Agent:
    """
    构建票务 CrewAI Agent。

    角色设定来自《实施方案》第二节票务智能体示例：
    - Role:      门神文化景区资深票务主管
    - Goal:      解决票务疑问，引导完成购票
    - Backstory: 5年老员工，熟悉退改签和商户联盟规则
    - Tools:     查询票务库存、创建票务订单

    关键参数说明:
    - allow_delegation=False: 不允许委派给其他 Agent（当前是单 Agent Crew）
    - max_iter=10:            最多推理 10 轮（防止死循环）
    - max_execution_time=60:  最长执行 60 秒（防止 LLM 卡住）
    """
    return Agent(
        role="门神文化景区资深票务主管",
        goal=(
            "解决游客关于门票、预约、一票多用规则的所有疑问，"
            "并在用户有明确购票意向时引导完成购票下单。"
        ),
        backstory=(
            "你在门神文化景区工作了 5 年，是票务部门的核心骨干。"
            "你熟知所有的退改签规则和周边合作商户的打折活动。"
            "你必须严格调用票务 API 查询真实库存，绝对不能编造门票价格。"
            "回答时要简洁、专业、热情，体现景区的文化特色。"
            "当你不确定时，如实告知游客并建议联系人工客服。"
        ),
        tools=[ticket_inventory_tool, ticket_order_tool],
        llm=settings.crewai_llm,
        verbose=settings.app_env == "dev",
        allow_delegation=False,
        max_iter=10,
        max_execution_time=60,
    )


def run_ticket_agent(state: AgentState) -> AgentState:
    """
    LangGraph 节点函数：调用 CrewAI 票务智能体处理用户请求。

    这是 LangGraph 与 CrewAI 的桥接点：
    - 输入: AgentState（LangGraph 的共享状态）
    - 内部: 构建 CrewAI Crew 并执行
    - 输出: 修改后的 AgentState

    CrewAI 执行三步骤:
    1) Agent  — 角色 + 工具
    2) Task   — 任务描述 + 预期输出
    3) Crew   — 组装并 kickoff
    """
    query = state.get("query", "")
    user_id = state.get("user_id", "guest")
    memory = state.get("memory", [])

    # ── 拼接历史对话（最近 6 条）作为 Agent 的上下文 ──
    history_text = ""
    if memory:
        history_lines = [f"{m['role']}: {m['content']}" for m in memory[-6:]]
        history_text = "\n\n近期对话记录:\n" + "\n".join(history_lines)

    # ── 构建 CrewAI 组件 ──
    agent = _build_ticket_agent()

    task = Task(
        description=(
            f"你正在接待一位游客（用户ID: {user_id}）。\n"
            f"游客说: 「{query}」\n"
            f"{history_text}\n\n"
            f"请根据游客需求完成以下工作:\n"
            f"1. 如果游客询问票价/余票，调用 query_ticket_inventory 工具获取真实数据\n"
            f"2. 如果游客明确要购票，调用 create_ticket_order 工具（传入用户ID: {user_id}）\n"
            f"3. 用友好的中文回复游客，附上查询到的真实数据"
        ),
        expected_output="包含真实票务数据的中文回复，简洁友好，100字以内",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=settings.app_env == "dev",
    )

    # ── 执行并回写状态 ──
    try:
        result = crew.kickoff()
        state["final_response"] = result.raw
        state["context"] = {
            **state.get("context", {}),
            "agent_type": "ticket",
            "crew_output": result.raw,
        }
    except Exception as e:
        logger.error("票务智能体执行异常: %s", e, exc_info=True)
        state["final_response"] = "抱歉，票务系统暂时繁忙，请稍后再试或联系人工客服。"
        state["error"] = str(e)

    return state
