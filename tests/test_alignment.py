"""alignment_check 测试（从原 pipelines/test_alignment.py 迁移标准化）。"""
from alignment_check import get_new_public_nodes_since

from cyber_planner import CyberBrainStore


def test_no_new_public_nodes_returns_empty(tmp_env):
    result = get_new_public_nodes_since(
        since_iso="2099-01-01T00:00:00+00:00",  # 未来时间 → 无新节点
        kg_path=tmp_env["kg_path"],
    )
    assert result == []


def test_new_public_nodes_returned(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    store.create(layer="Ego", event_label="新公开节点", description="d",
                 evidence="e", visibility="public")
    result = get_new_public_nodes_since(
        since_iso="2000-01-01T00:00:00+00:00",
        kg_path=tmp_env["kg_path"],
    )
    assert any("新公开节点" in (n.get("event_label") or "") for n in result)


def test_only_public_nodes_included(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    store.create(layer="Ego", event_label="私有节点", description="d",
                 evidence="e", visibility="private")
    result = get_new_public_nodes_since(
        since_iso="2000-01-01T00:00:00+00:00",
        kg_path=tmp_env["kg_path"],
    )
    assert all(n.get("visibility") == "public" for n in result)
