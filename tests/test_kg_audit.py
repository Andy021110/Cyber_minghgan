"""
tests/test_kg_audit.py — 三层结构审计脚本的测试

重点守护一个坑：**标签泄漏**。
节点描述里常直接写着「Id层」「超我」，不抹掉的话分类器靠认层名就能高分，
可分性结论会严重虚高（实测 0.767 → 抹掉后 0.589）。
"""

from cyber_planner import CyberBrainStore
from pipelines.kg_layer_audit import (
    MultinomialNB,
    audit,
    ngrams,
    node_text,
    node_text_clean,
    scrub_layer_tokens,
)


def test_scrub_removes_layer_tokens():
    text = "Id层的本能冲动 vs 超我对自己的应然焦虑，Ego 做现实协商"
    cleaned = scrub_layer_tokens(text)
    for tok in ("Id", "Ego", "超我", "本我", "自我"):
        assert tok not in cleaned
    # 非层名内容应保留
    assert "本能冲动" in cleaned
    assert "应然焦虑" in cleaned


def test_node_text_clean_keeps_semantics():
    node = {"event_label": "快感原则主导", "description": "Id层表现出逃避冲动"}
    assert "Id" in node_text(node)
    assert "Id" not in node_text_clean(node)
    assert "逃避冲动" in node_text_clean(node)


def test_scrubbing_reduces_layer_signal():
    """抹掉层名后，文本里不应再出现任何层名变体（大小写都要处理）。"""
    raw = node_text({"event_label": "Superego 的道德约束", "description": "superego 内化规范"})
    clean = node_text_clean({"event_label": "Superego 的道德约束", "description": "superego 内化规范"})
    assert "Superego" in raw
    assert "uperego" not in clean


def test_nb_learns_separable_classes():
    docs = [["a", "a", "b"], ["a", "b"], ["x", "y", "z"], ["x", "y"]]
    labels = ["p", "p", "q", "q"]
    clf = MultinomialNB()
    clf.fit(docs, labels)
    assert clf.predict(["a", "a"]) == "p"
    assert clf.predict(["x", "z"]) == "q"


def test_ngrams_handles_short_text():
    assert ngrams("") == []
    assert ngrams("短") == ["短"]
    assert len(ngrams("abcdef", n=3)) == 4


def _make_node(layer, label, desc, uuid):
    return {
        "uuid": uuid,
        "layer": layer,
        "event_label": label,
        "description": desc,
        "evidence": "证据",
        "batch_id": "Test",
        "round_refs": [],
        "created_at": "2026-08-29T00:00:00+00:00",
        "importance": 5,
        "access_count": 0,
        "last_accessed_at": None,
        "archived": False,
        "archived_at": None,
        "archive_reason": None,
        "source_mode": "test",
        "visibility": "private",
    }


def test_audit_report_shape(tmp_env):
    """审计脚本在合成 KG 上能跑通并返回完整结构。"""
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    # tmp_env 拷的是真实 KG，三层都要清空，否则会把真实节点算进来
    for lst in store._node_lists():
        lst.clear()
    layer_list = store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]
    for i in range(12):
        layer_list.append(
            _make_node("Ego", f"现实协商{i}", "面对冲突时的理性化防御", f"e{i}")
        )
        layer_list.append(
            _make_node("Id", f"本能冲动{i}", "快感原则驱动的逃避冲动", f"i{i}")
        )
        layer_list.append(
            _make_node("Superego", f"道德焦虑{i}", "内化的应然焦虑与自我批判", f"s{i}")
        )
    store._save()

    report = audit(tmp_env["kg_path"], folds=3)
    assert report["total_nodes"] == 36
    assert set(report["distribution"]) == {"Id", "Superego", "Ego"}
    assert "separability" in report and "separability_raw" in report
    # 抹掉层名后不应高于含层名的结果（泄漏只会高估）
    assert report["separability"]["cv_accuracy"] <= report["separability_raw"]["cv_accuracy"]
