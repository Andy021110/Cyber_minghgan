"""KG 修剪功能测试：重复扫描 / 归档 / 重要度提升（LLM 部分用 FakeAnthropic）。"""
from conftest import FakeAnthropic, FakeResponse, text_block

from cyber_planner import (
    CyberBrainStore,
    archive_node,
    boost_node_importance,
    get_prune_candidates,
    scan_duplicate_pairs,
)


def _store(tmp_env) -> CyberBrainStore:
    return CyberBrainStore(kg_path=tmp_env["kg_path"])


def test_scan_duplicate_pairs_no_dup(tmp_env):
    """LLM 判定无重叠 → 返回空列表。"""
    client = FakeAnthropic(script=[FakeResponse([text_block("[]")])])
    assert scan_duplicate_pairs(_store(tmp_env), client) == []
    assert client.messages.call_count == 1


def test_scan_duplicate_pairs_parses_json(tmp_env):
    """LLM 返回匹配对 JSON → 正确解析出 (uuid_a, uuid_b, reason)。"""
    store = _store(tmp_env)
    a = store.create(layer="Ego", event_label="深度工作", description="d", evidence="e")
    b = store.create(layer="Ego", event_label="深度专注", description="d", evidence="e")
    payload = '[{{"uuid_a":"{a}","uuid_b":"{b}","reason":"行为重叠"}}]'.format(
        a=a["uuid"][:8], b=b["uuid"][:8])
    client = FakeAnthropic(script=[FakeResponse([text_block(payload)])])
    pairs = scan_duplicate_pairs(store, client)
    assert len(pairs) == 1
    assert pairs[0]["reason"] == "行为重叠"
    assert pairs[0]["node_a"]["uuid"][:8] == a["uuid"][:8]
    assert pairs[0]["node_b"]["uuid"][:8] == b["uuid"][:8]


def test_archive_node_success(tmp_env):
    store = _store(tmp_env)
    node = store.create(layer="Id", event_label="待归档", description="d", evidence="e")
    result = archive_node(store, node["uuid"], reason="测试归档")
    assert result["success"] is True
    # 归档后不再出现在检索结果（retrieve 跳过 archived）
    assert store.retrieve("待归档", limit=5) == []


def test_archive_node_not_found(tmp_env):
    assert archive_node(_store(tmp_env), "不存在-uuid", "x") == {"success": False}


def test_boost_node_importance(tmp_env):
    store = _store(tmp_env)
    node = store.create(layer="Ego", event_label="重要节点", description="d", evidence="e",
                        importance=3)
    result = boost_node_importance(store, node["uuid"], new_importance=9)
    assert result["success"] is True
    assert result["new_importance"] == 9


def test_get_prune_candidates_shape(tmp_env):
    """候选结构：包含 nodes 键且为列表。"""
    cands = get_prune_candidates(_store(tmp_env))
    assert isinstance(cands, dict)
    assert isinstance(cands.get("nodes") or [], list)
