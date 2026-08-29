"""CyberBrainStore 核心 CRUD 与 visibility（从原 test_visibility/test_kg_browse 迁移标准化）。"""
from cyber_planner import CyberBrainStore


def _store(tmp_env) -> CyberBrainStore:
    return CyberBrainStore(kg_path=tmp_env["kg_path"])


def test_default_visibility_is_private(tmp_env):
    node = _store(tmp_env).create(
        layer="Ego", event_label="测试节点", description="描述", evidence="证据")
    assert node.get("visibility") == "private"


def test_explicit_public_visibility(tmp_env):
    node = _store(tmp_env).create(
        layer="Ego", event_label="公开节点", description="描述", evidence="证据",
        visibility="public")
    assert node.get("visibility") == "public"


def test_visibility_persisted(tmp_env):
    """create 时 visibility 落盘到 KG 文件（retrieve 是 LLM 精简摘要，不含该字段）。"""
    import json
    path = tmp_env["kg_path"]
    store = CyberBrainStore(kg_path=path)
    node = store.create(layer="Id", event_label="持久化节点", description="d",
                        evidence="e", visibility="public")
    kg = json.loads(path.read_text(encoding="utf-8"))
    nodes = kg["nodes"]["Cyber_Minghan"]["Id_Dynamics"]  # layer_key 映射
    hit = [n for n in nodes if n.get("uuid") == node.get("uuid")]
    assert hit and hit[0].get("visibility") == "public"


def test_retrieve_by_keyword(tmp_env):
    store = _store(tmp_env)
    store.create(layer="Ego", event_label="深度工作偏好", description="专注时关闭通知",
                 evidence="测试", visibility="private")
    hits = store.retrieve("深度工作", limit=5)
    assert any("深度工作" in (h.get("event_label") or "") for h in hits)


def test_update_node(tmp_env):
    store = _store(tmp_env)
    node = store.create(layer="Ego", event_label="旧标签", description="旧",
                        evidence="e")
    key = node.get("uuid") or node.get("id")
    updated = store.update(key, description="新描述")
    assert updated.get("description") == "新描述"


def test_delete_node(tmp_env):
    store = _store(tmp_env)
    node = store.create(layer="Id", event_label="待删除", description="d", evidence="e")
    key = node.get("uuid") or node.get("id")
    assert store.delete(key) is True
    assert store.retrieve(key, limit=5) == []  # retrieve 不存在返回空列表


def test_create_sets_uuid_and_timestamp(tmp_env):
    node = _store(tmp_env).create(layer="Ego", event_label="字段完整", description="d", evidence="e")
    assert node.get("uuid") or node.get("id")
    assert node.get("created_at") or node.get("timestamp")
