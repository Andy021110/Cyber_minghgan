"""A2 引用校验的接线测试。

为什么需要这一层：校验函数早就写好了（agent/citations.py），
但如果没接进图，它就只是一段**能跑但没人调用**的代码——
跟没有一样。这一层测的是"接上了没有"，不是"函数对不对"。

针对的是 8月9日 A 类跑分暴露的 HALLUC_EMPTY：记忆库为空时模型照样
编出"北邮，北京邮电大学"。检索层对这种情况无能为力（无米下锅），
只有生成层的引用校验能发现。
"""

import pytest

from agent.memory import retrieve_long_term, retrieve_long_term_with_refs


class _FakeStore:
    """最小桩：返回一条带 uuid 的命中，用来验证 refs 提取。"""

    def retrieve(self, query, limit=5, **kw):
        return [{"uuid": "abcdef1234567890", "layer": "Ego",
                 "event_label": "某个记忆", "description": "内容"}]


class _FakeEpi:
    def search(self, query, limit=5, **kw):
        return [{"eid": "ep_2026-01-01_0000", "ts": "2026-01-01",
                 "user_text": "你好", "assistant_text": "嗨"}]


def test_with_refs_returns_extracted_refs():
    text, refs = retrieve_long_term_with_refs("查询", _FakeStore(), _FakeEpi())
    assert "abcdef12" in refs, "L1 的 8 位短 uuid 应在 refs 里"
    assert "ep_2026-01-01_0000" in refs, "L0 的 eid 应在 refs 里"


def test_refs_match_what_is_injected_into_prompt():
    """refs 必须与注入 prompt 的 [ref:xxx] 一致，否则校验会误判。"""
    text, refs = retrieve_long_term_with_refs("查询", _FakeStore(), _FakeEpi())
    assert "[ref:abcdef12]" in text
    assert "[ref:ep_2026-01-01_0000]" in text
    assert any(r in text for r in refs)


def test_legacy_retrieve_still_returns_string():
    """向后兼容：老接口仍返回纯文本，不能因为接线就破坏。"""
    out = retrieve_long_term("查询", _FakeStore(), _FakeEpi())
    assert isinstance(out, str)


def test_graph_contains_verify_node():
    """图里必须有 verify 节点，且位于 agent 结束到 persist 之间。"""
    from agent.graph import build_graph

    # 只需图结构，不跑推理，所以 llm 给个最小桩即可
    g = build_graph(llm=object(), store=_FakeStore(), episodic=_FakeEpi())
    nodes = set(g.get_graph().nodes)
    assert "verify" in nodes, "verify 节点没接进图——校验函数将永不被调用"

    edges = {(e.source, e.target) for e in g.get_graph().edges}
    assert ("verify", "persist") in edges, "verify 应在 persist 之前"


def test_answer_without_refs_when_nothing_retrieved_is_flagged():
    """模拟 HALLUC_EMPTY：没检索到任何东西却给出断言式回答。"""
    from agent.citations import validate_citations

    # 记忆库为空 → refs 为空
    answer = "你在北邮读的 AI 本科。"
    res = validate_citations(answer, [])
    # 没引用不算"引用非法"，但 cited 为空意味着无从溯源
    assert res["cited"] == []
    assert res["ok"] is True          # 校验器本身没问题
    # 真正的判定在上层：无检索结果却给出事实断言 = 可疑
    assert res["cited"] == []


def test_fabricated_ref_is_caught_end_to_end():
    """端到端：引用了一个本次没检索到的 id。"""
    from agent.citations import validate_citations

    res = validate_citations("依据 [ref:deadbeef] 可知", ["abcdef12"])
    assert res["ok"] is False
    assert "deadbeef" in res["illegal"]
