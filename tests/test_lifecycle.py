"""
tests/test_lifecycle.py — 自动遗忘（Phase 2b）单元测试

覆盖：时间解析、半衰期衰减数学、遗忘候选筛选、归档执行与幂等性。
"""

from datetime import datetime, timedelta, timezone

import pytest

from memory.lifecycle import (
    DEFAULT_HALF_LIFE_DAYS,
    apply_forgetting,
    days_since,
    effective_importance,
    forget_candidates,
    parse_ts,
)


def _node(uuid, importance=5, age_days=0, accessed_age_days=None, archived=False):
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=age_days)).isoformat()
    node = {
        "uuid": uuid,
        "layer": "Ego",
        "event_label": f"节点-{uuid}",
        "description": "描述",
        "evidence": "证据",
        "created_at": created,
        "importance": importance,
        "archived": archived,
        "last_accessed_at": None,
    }
    if accessed_age_days is not None:
        node["last_accessed_at"] = (now - timedelta(days=accessed_age_days)).isoformat()
    return node


def test_parse_ts_handles_z_and_offset():
    assert parse_ts("2026-01-01T00:00:00+00:00") is not None
    assert parse_ts("2026-01-01T00:00:00Z") is not None
    assert parse_ts("") is None
    assert parse_ts("not-a-date") is None


def test_days_since_zero_for_missing_timestamp():
    assert days_since(None) == 0.0
    assert days_since("garbage") == 0.0


def test_days_since_counts_real_days():
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert 9.5 < days_since(past) < 10.5


def test_effective_importance_half_life():
    node = _node("a", importance=8, age_days=DEFAULT_HALF_LIFE_DAYS)
    # 过一个半衰期，有效重要性减半：8 → 4
    assert effective_importance(node) == pytest.approx(4.0, abs=0.05)


def test_effective_importance_has_floor():
    node = _node("b", importance=5, age_days=365 * 20)
    assert effective_importance(node) == 0.5


def test_effective_importance_prefers_last_accessed():
    """最近被访问过的节点不应按创建时间衰减。"""
    node = _node("c", importance=8, age_days=1000, accessed_age_days=0)
    assert effective_importance(node) == pytest.approx(8.0, abs=0.05)


def test_forget_candidates_selects_old_low_value_only():
    now = datetime.now(timezone.utc)
    nodes = [
        _node("old_low", importance=3, age_days=400),   # 有效 ~0.75 → 候选
        _node("old_high", importance=10, age_days=400),  # 有效 ~2.5 → 保留
        _node("new_low", importance=1, age_days=5),      # 太新 → 保留
        _node("archived", importance=1, age_days=999, archived=True),
    ]
    cands = forget_candidates(nodes, now=now)
    uuids = [c["uuid"] for c in cands]
    assert "old_low" in uuids
    assert "old_high" not in uuids
    assert "new_low" not in uuids
    assert "archived" not in uuids


def test_apply_forgetting_archives_and_is_idempotent(tmp_env):
    from cyber_planner import CyberBrainStore

    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    layer = store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]
    layer.append(_node("doomed", importance=2, age_days=500))
    store._save()

    archived = apply_forgetting(store)
    assert [a["uuid"] for a in archived] == ["doomed"]

    reloaded = CyberBrainStore(kg_path=tmp_env["kg_path"])
    target = [n for lst in reloaded._node_lists() for n in lst if n.get("uuid") == "doomed"][0]
    assert target["archived"] is True
    assert "auto-forget" in (target.get("archive_reason") or "")

    # 幂等：再次执行不应重复归档
    assert apply_forgetting(reloaded) == []


def test_apply_forgetting_dry_run_does_not_write(tmp_env):
    from cyber_planner import CyberBrainStore

    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"].append(
        _node("dry", importance=1, age_days=500)
    )
    store._save()

    cands = apply_forgetting(store, dry_run=True)
    assert [c["uuid"] for c in cands] == ["dry"]

    reloaded = CyberBrainStore(kg_path=tmp_env["kg_path"])
    target = [n for lst in reloaded._node_lists() for n in lst if n.get("uuid") == "dry"][0]
    assert target["archived"] is False
