"""对外可见性硬隔离（BC-002 / A1）的回归测试。

覆盖范围刻意包含 **L0 原文**而不只是 KG：
L0 是对话原文，比 KG 摘要更私密。只做 KG 过滤会留下"看起来安全、
其实原文全漏"的虚假安全感——2026-08-30 复核时发现 L0 当时连
visibility 字段都没有。

关键设计：`audience` 是模式（谁在问），不是让调用方指定可见性。
后者一旦传错或图省事传 None，私密内容就直接泄露且从调用点看不出错。
"""
import pytest

from cyber_planner import CyberBrainStore
from memory.episodic_store import EpisodicStore


def _store(tmp_env):
    return CyberBrainStore(kg_path=tmp_env["kg_path"])


def _seed_kg(store):
    store.create(layer="Ego", event_label="公开项目", description="可对外",
                 evidence="e", visibility="public")
    store.create(layer="Id", event_label="私密情感", description="不可对外",
                 evidence="e", visibility="private")
    store.create(layer="Ego", event_label="无标注节点", description="缺字段",
                 evidence="e")


# ── KG（L1）──

def test_external_excludes_private_and_unlabeled(tmp_env):
    """BC-002 回归：private 与**无标注**节点在对外模式下都不可见。"""
    store = _store(tmp_env)
    _seed_kg(store)
    labels = {h["event_label"] for h in store.retrieve("项目", audience="external")}
    assert "私密情感" not in labels
    hits = store.retrieve("无标注", audience="external")
    assert "无标注节点" not in {h["event_label"] for h in hits}


def test_external_includes_public(tmp_env):
    """只测"不泄露"会漏掉空集假通过——必须同时验证 public 确实能召回。"""
    store = _store(tmp_env)
    _seed_kg(store)
    labels = {h["event_label"] for h in store.retrieve("公开", audience="external")}
    assert "公开项目" in labels


def test_internal_is_unaffected(tmp_env):
    """自用模式保持原样，不能为了对外安全而牺牲内部可用性。"""
    store = _store(tmp_env)
    _seed_kg(store)
    labels = {h["event_label"] for h in store.retrieve("私密", audience="internal")}
    assert "私密情感" in labels


def test_invalid_audience_raises(tmp_env):
    """拼错 audience 必须炸，而不是悄悄退化成 internal（那等于泄露）。"""
    with pytest.raises(ValueError, match="audience 必须是"):
        _store(tmp_env).retrieve("x", audience="publik")


# ── L0 原文 ──

def test_l0_external_hides_private_by_default(tmp_env):
    """L0 默认 private：旧数据反序列化也走该默认值，External 下不可见。"""
    epi = EpisodicStore(tmp_env["epi_path"])
    epi.append(ts="2026-05-01", user_text="我暗恋过一个人，从没说过",
               assistant_text="记住了")
    assert epi.search("暗恋", audience="external") == []


def test_l0_external_includes_public(tmp_env):
    """标注为 public 的原文对外可见——否则对外模式等于全空。"""
    epi = EpisodicStore(tmp_env["epi_path"])
    epi.append(ts="2026-05-02", user_text="我在做一个记忆项目",
               assistant_text="记住了", visibility="public")
    hits = epi.search("记忆项目", audience="external")
    assert hits and "记忆项目" in hits[0].get("user_text", "")


def test_l0_internal_still_sees_private(tmp_env):
    epi = EpisodicStore(tmp_env["epi_path"])
    epi.append(ts="2026-05-03", user_text="私密原文内容", assistant_text="嗯")
    assert epi.search("私密原文", audience="internal")


def test_l0_invalid_audience_raises(tmp_env):
    with pytest.raises(ValueError, match="audience 必须是"):
        EpisodicStore(tmp_env["epi_path"]).search("x", audience="extern")


def test_episode_visibility_defaults_private(tmp_env):
    """默认值必须是 private——安全默认不能反过来。"""
    epi = EpisodicStore(tmp_env["epi_path"])
    epi.append(ts="2026-05-04", user_text="x", assistant_text="y")
    assert epi.search("x")[0]["visibility"] == "private"
