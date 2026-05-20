"""
LLM API 连通性 + 全链路测试脚本。

使用方法（在项目根目录执行）:
    python -m tests.test_llm

测试内容:
    1. LLM 基础连通性
    2. 意图分类准确性（7 类意图）
    3. 会话持久化（SessionStore 读写）
    4. 人工审核队列（ReviewQueue 读写）
    5. 完整 LangGraph 工作流（全部 5 类场景 + 未登录）
"""

from __future__ import annotations

import os
import sys
import time


def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_1_llm_connection():
    """测试 1：LLM 基础连通性"""
    _separator("测试 1：LLM 基础连通性")

    from app.core.config import settings
    import litellm

    print(f"当前 LLM 配置: {settings.crewai_llm}")
    print(f"DEEPSEEK_API_KEY: {'已设置' if os.environ.get('DEEPSEEK_API_KEY') else '未设置'}")
    print(f"DASHSCOPE_API_KEY: {'已设置' if os.environ.get('DASHSCOPE_API_KEY') else '未设置'}")
    print(f"OPENAI_API_KEY: {'已设置' if os.environ.get('OPENAI_API_KEY') else '未设置'}")
    print()

    start = time.time()
    try:
        response = litellm.completion(
            model=settings.crewai_llm,
            messages=[{"role": "user", "content": "你好，请回复'连接成功'四个字"}],
            temperature=0,
            max_tokens=20,
        )
        reply = response.choices[0].message.content.strip()
        elapsed = time.time() - start
        print(f"[PASS] LLM 返回: {reply}")
        print(f"       耗时: {elapsed:.2f}s, 模型: {response.model}")
        return True
    except Exception as e:
        print(f"[FAIL] LLM 调用失败: {e}")
        return False


def test_2_intent_classification():
    """测试 2：意图分类准确性（7 类）"""
    _separator("测试 2：LLM 意图分类（7 类）")

    from app.graph import _llm_classify, _keyword_classify

    test_cases = [
        ("今天门票多少钱？", "ticket"),
        ("帮我买两张明天的票", "ticket"),
        ("有什么适合小学生的研学课程？", "study"),
        ("景区几点开门？", "customer_service"),
        ("停车场在哪里？", "customer_service"),
        ("帮我写一段抖音文案", "content"),
        ("做一个门神主题的公众号推文", "content"),
        ("有什么门神纪念品推荐？", "ecommerce"),
        ("查一下我的文创订单物流", "ecommerce"),
        ("给我看今天的运营日报", "admin"),
        ("本周GMV和退款率怎么样", "admin"),
        ("今天天气不错", "unknown"),
    ]

    print("--- LLM 分类 ---")
    llm_pass = 0
    for query, expected in test_cases:
        try:
            result = _llm_classify(query)
            ok = result == expected
            if ok:
                llm_pass += 1
            print(f"  [{'PASS' if ok else 'MISS'}] '{query}' -> {result} (期望: {expected})")
        except Exception as e:
            print(f"  [FAIL] '{query}' -> 异常: {e}")
    print(f"\nLLM 准确率: {llm_pass}/{len(test_cases)}")

    print("\n--- 关键词兜底（对照组）---")
    kw_pass = 0
    for query, expected in test_cases:
        result = _keyword_classify(query)
        ok = result == expected
        if ok:
            kw_pass += 1
        print(f"  [{'PASS' if ok else 'MISS'}] '{query}' -> {result} (期望: {expected})")
    print(f"\n关键词准确率: {kw_pass}/{len(test_cases)}")
    return llm_pass >= len(test_cases) - 2


def test_3_session_store():
    """测试 3：会话持久化"""
    _separator("测试 3：SessionStore 持久化")

    from app.core.memory import session_store

    test_sid = "test-session-001"
    test_memory = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "欢迎光临门神文化景区！"},
    ]

    session_store.save_memory(test_sid, "test_user", test_memory)
    loaded = session_store.get_memory(test_sid)

    if loaded == test_memory:
        print(f"[PASS] 写入并读取成功: {len(loaded)} 条记录")
    else:
        print(f"[FAIL] 读取不匹配: {loaded}")
        return False

    sessions = session_store.list_sessions(limit=5)
    print(f"[PASS] 会话列表: {len(sessions)} 条")
    return True


def test_4_review_queue():
    """测试 4：人工审核队列"""
    _separator("测试 4：ReviewQueue 审核队列")

    from app.core.review import review_queue as rq

    rid = rq.submit(
        session_id="test-session-001",
        user_id="test_user",
        query="退票怎么操作",
        agent_response="未使用门票支持提前1天退改...",
        intent="customer_service",
    )
    print(f"[PASS] 提交审核: {rid}")

    pending = rq.list_pending()
    print(f"[PASS] 待审列表: {len(pending)} 条")

    item = rq.get(rid)
    assert item and item["status"] == "pending"
    print(f"[PASS] 查询审核: status={item['status']}")

    rq.complete(rid, approved=True, reviewer_note="测试通过")
    item = rq.get(rid)
    assert item and item["status"] == "approved"
    print(f"[PASS] 完成审核: status={item['status']}")
    return True


def test_5_full_graph():
    """测试 5：完整 LangGraph 工作流（全部场景）"""
    _separator("测试 5：完整 LangGraph 工作流")

    from app.graph import app_graph

    cases = [
        {"name": "票务", "query": "明天的门票还有吗？"},
        {"name": "研学", "query": "有什么适合8岁孩子的研学课？"},
        {"name": "客服", "query": "景区地址在哪里？"},
        {"name": "内容运营", "query": "帮我写一段门神文化的抖音文案"},
        {"name": "文创电商", "query": "有什么门神主题的纪念品？"},
        {"name": "管理后台", "query": "给我看今天的运营日报"},
        {"name": "未登录", "query": "买票", "_auth": False},
    ]

    all_pass = True
    for c in cases:
        auth = c.get("_auth", True)
        state = {
            "session_id": f"test-{c['name']}",
            "user_id": "u_test",
            "query": c["query"],
            "authenticated": auth,
            "memory": [],
            "context": {},
            "metadata": {},
        }
        print(f"--- {c['name']} ---")
        print(f"  query: {c['query']}")
        start = time.time()
        try:
            result = app_graph.invoke(state)
            elapsed = time.time() - start
            print(f"  intent: {result.get('intent', 'N/A')}")
            resp = result.get("final_response", "(空)")
            print(f"  response: {resp[:120]}{'...' if len(resp)>120 else ''}")
            print(f"  耗时: {elapsed:.2f}s")
            if result.get("error"):
                print(f"  error: {result['error']}")
                all_pass = False
        except Exception as e:
            print(f"  [FAIL] {e}")
            all_pass = False
        print()

    return all_pass


if __name__ == "__main__":
    print("Agent Hub — 全链路测试")
    print(f"Python: {sys.version}")
    print(f"工作目录: {os.getcwd()}")

    results = {}
    results["LLM连通"] = test_1_llm_connection()

    if results["LLM连通"]:
        results["意图分类"] = test_2_intent_classification()
        results["会话持久化"] = test_3_session_store()
        results["审核队列"] = test_4_review_queue()
        results["完整工作流"] = test_5_full_graph()
    else:
        print("\n[SKIP] LLM 连接失败，跳过后续测试。")

    _separator("测试汇总")
    for name, passed in results.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print()
    sys.exit(0 if all(results.values()) else 1)
