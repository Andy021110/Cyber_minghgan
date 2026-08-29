"""
tests/test_versioning.py — 记忆冲突与版本化（Phase 2c）单元测试

覆盖：版本递增、历史快照与上限、supersede 取代链、冲突检测。
"""

from datetime import datetime, timedelta, timezone

from cyber_planner import CyberBrainStore
from memory.versioning import (
    conflict_candidates,
    normalize_label,
    supersede,
    update_with_version,
)


def _make_node(uuid, label="喜欢美式", created_days_ago=0, **extra):
    node = {
        "uuid": uuid,
        "layer": "Ego",
        "event_label": label,
        "description": "描述文本",
        "evidence": "证据文本",
        "batch_id": "Test",
        "round_refs": [],
        "created_at": (datetime.now(timezone.utc)
                       - timedelta(days=created_days_ago)).isoformat(),
        "importance": 5,
        "access_count": 0,
        "last_accessed_at": None,
        "archived": False,
        "archived_at": None,
        "archive_reason": None,
        "source_mode": "test",
        "visibility": "private",
        "version": 1,
    }
    node.update(extra)
    return node


def _find(store, uuid):
    for lst in store._node_lists():
        for i, n in enumerate(lst):
            if n.get("uuid") == uuid:
                return lst[i]
    raise AssertionError(f"节点不存在: {uuid}")


def test_normalize_label_strips_punctuation():
    assert normalize_label(" 喜欢 美式！") == "喜欢美式"
    assert normalize_label("喜欢，美式") == "喜欢美式"


def test_update_with_version_bumps_version_and_records_history(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"].append(_make_node("v1"))
    store._save()

    updated = update_with_version(store, "v1", {"description": "改喝手冲了"})

    assert updated["version"] == 2
    assert updated["description"] == "改喝手冲了"
    assert updated["updated_by"] == "system"
    assert len(updated["history"]) == 1
    assert updated["history"][0]["description"] == "描述文本"
    assert updated["history"][0]["version"] == 1


def test_history_is_capped(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"].append(_make_node("cap"))
    store._save()

    for i in range(8):
        update_with_version(store, "cap", {"description": f"第{i}版"}, history_limit=3)

    node = _find(store, "cap")
    assert node["version"] == 9
    assert len(node["history"]) == 3, "history 必须有上限，否则节点无限膨胀"


def test_supersede_links_old_and_new(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"].append(_make_node("old1"))
    store._save()

    new_node = supersede(
        store,
        "old1",
        {"event_label": "喜欢手冲", "description": "从美式转到手冲", "evidence": "用户自己说的"},
    )

    old = _find(store, "old1")
    assert old["archived"] is True
    assert old["superseded_by"] == new_node["uuid"]
    assert new_node["supersedes"] == "old1"
    assert new_node["version"] == 1
    assert new_node["event_label"] == "喜欢手冲"

    # 旧节点归档后不应再被检索到
    hits = store.retrieve("喜欢美式")
    assert all(h["uuid"] != "old1" for h in hits)


def test_conflict_candidates_detects_duplicate_labels(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    layer = store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]
    layer.append(_make_node("c1", label="喜欢美式！", created_days_ago=10))
    layer.append(_make_node("c2", label="喜欢美式", created_days_ago=1))
    layer.append(_make_node("c3", label="完全不同的标签"))
    store._save()

    conflicts = conflict_candidates(store)
    matched = [c for c in conflicts if c["label"] == "喜欢美式"]
    assert len(matched) == 1
    assert matched[0]["count"] == 2
    assert {n["uuid"] for n in matched[0]["nodes"]} == {"c1", "c2"}
    assert all(c["label"] != "完全不同的标签" for c in conflicts)


def test_conflict_candidates_ignores_archived(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    layer = store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]
    layer.append(_make_node("a1", label="重复标签"))
    layer.append(_make_node("a2", label="重复标签", archived=True))
    store._save()

    conflicts = [c for c in conflict_candidates(store) if c["label"] == "重复标签"]
    assert conflicts == [], "已归档节点不应参与冲突检测"
