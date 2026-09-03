"""来源可信度（BC-011）的测试。

为什么需要它：写入端原本不记录"内容从哪来"，于是任何能跟 Agent 说上话的人
都能往记忆里塞东西，而记忆会被当作可信输入驱动后续行为。竞品实测：
    MINJA        仅靠对话交互即可 98.2% 注入恶意记录
    Trojan Hippo 一次不可信工具调用植入休眠 payload，跨 100 个会话后触发
    AgentPoison  <0.1% 投毒率即可劫持，且功能测试看不出来
一旦 Agent 有工具调用能力，被投毒的记忆就是远程控制面。
"""

import pytest

from cyber_planner import (
    TRUST_CONVERSATION, TRUST_EXTERNAL, TRUST_SELF, TRUST_UNTRUSTED,
    CyberBrainStore, trust_of,
)


def _make(store, label, **kw):
    return store.create(layer="Ego", event_label=label,
                        description=f"{label}的描述", evidence="e", **kw)


# ── 写入时标注 ──

def test_create_defaults_to_conversation(tmp_env):
    n = _make(CyberBrainStore(kg_path=tmp_env["kg_path"]), "默认来源")
    assert n["source_trust"] == TRUST_CONVERSATION


def test_create_accepts_each_level(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    for lvl in (TRUST_SELF, TRUST_CONVERSATION, TRUST_EXTERNAL, TRUST_UNTRUSTED):
        assert _make(store, f"节点-{lvl}", source_trust=lvl)["source_trust"] == lvl


def test_illegal_trust_is_rejected(tmp_env):
    """非法值必须炸，不能默默写进去——否则过滤时会出现无法归类的记录。"""
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    with pytest.raises(ValueError, match="非法 source_trust"):
        _make(store, "坏来源", source_trust="totally-trusted")


# ── 既有数据（无该字段）的兼容 ──

def test_missing_field_treated_as_conversation():
    """既有 146 条没有这个字段，不能一步掉到最低档。

    若默认 untrusted，等于用一次改动废掉全部历史记忆——
    conversation 才是它们的真实来源。
    """
    assert trust_of({}) == TRUST_CONVERSATION
    assert trust_of({"source_trust": None}) == TRUST_CONVERSATION


def test_unknown_value_falls_back_to_conversation():
    """字段存在但取值不认识时，也按 conversation 处理而不是崩溃。"""
    assert trust_of({"source_trust": "whatever"}) == TRUST_CONVERSATION


# ── 检索过滤（核心能力）──

def test_min_trust_filters_out_untrusted(tmp_env):
    """不可信来源必须能被挡在工具调用之外。"""
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    _make(store, "被投毒的指令", source_trust=TRUST_UNTRUSTED)
    _make(store, "正常对话内容", source_trust=TRUST_CONVERSATION)

    hits = store.retrieve("内容", min_trust=TRUST_EXTERNAL)
    labels = {h["event_label"] for h in hits}
    assert "被投毒的指令" not in labels


def test_min_trust_self_keeps_only_self(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    _make(store, "本人明确说的", source_trust=TRUST_SELF)
    _make(store, "对话里推测的", source_trust=TRUST_CONVERSATION)

    hits = store.retrieve("的", min_trust=TRUST_SELF)
    assert {h["event_label"] for h in hits} == {"本人明确说的"}


def test_no_min_trust_returns_everything(tmp_env):
    """不传 min_trust 时行为不变——向后兼容，不影响既有调用。"""
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    _make(store, "不可信内容", source_trust=TRUST_UNTRUSTED)
    assert any(h["event_label"] == "不可信内容"
               for h in store.retrieve("不可信内容"))


def test_illegal_min_trust_is_rejected(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    with pytest.raises(ValueError, match="非法 min_trust"):
        store.retrieve("x", min_trust="kinda-trusted")


def test_legacy_nodes_survive_external_filter(tmp_env):
    """真实 KG 的 146 条没有该字段，按 conversation 处理应当通过 EXTERNAL 过滤。"""
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    hits = store.retrieve("明翰", limit=10, min_trust=TRUST_EXTERNAL)
    assert hits, "既有记忆不该因为缺字段而被新的过滤条件挡掉"
