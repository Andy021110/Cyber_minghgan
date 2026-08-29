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


# ── 持久化安全性（回归测试）──────────────────────────────────────
# 原实现用 write_text 直接覆写 KG：写到一半进程被杀会留下半截 JSON，
# 而 KG 是唯一数据源且无备份 → 记忆不可恢复。
# 改为「临时文件 + os.replace 原子替换 + 保留 .bak」。

def test_save_leaves_no_temp_file(tmp_env):
    _store(tmp_env).create(layer="Ego", event_label="落盘", description="d", evidence="e")
    leftovers = list(tmp_env["kg_path"].parent.glob("*.tmp"))
    assert leftovers == [], f"临时文件未清理：{leftovers}"


def test_save_creates_backup_of_previous_state(tmp_env):
    store = _store(tmp_env)
    store.create(layer="Ego", event_label="第一次", description="d1", evidence="e")
    bak = tmp_env["kg_path"].with_suffix(tmp_env["kg_path"].suffix + ".bak")
    assert bak.exists(), "保存后应保留上一次成功状态的备份"

    store.create(layer="Ego", event_label="第二次", description="d2", evidence="e")
    current = tmp_env["kg_path"].read_text(encoding="utf-8")
    backup = bak.read_text(encoding="utf-8")
    assert "第二次" in current
    assert "第二次" not in backup, ".bak 应保存上一次的状态，而不是最新状态"


def test_saved_file_is_valid_json_after_each_write(tmp_env):
    """每次写入后主文件都必须能被完整解析（原子写的直接目的）。"""
    import json

    store = _store(tmp_env)
    for i in range(3):
        store.create(layer="Id", event_label=f"节点{i}", description="d", evidence="e")
        data = json.loads(tmp_env["kg_path"].read_text(encoding="utf-8"))
        assert "nodes" in data


def _add_interaction(path, event, trigger, resolution):
    """往 KG **顶层** interactions 塞一条（注意不在 nodes.Cyber_Minghan 下）。"""
    import json
    kg = json.loads(path.read_text(encoding="utf-8"))
    kg.setdefault("interactions", []).append({
        "event": event, "trigger": trigger, "resolution": resolution,
        "batch_id": "test", "timestamp": "2026-01-01 00:00:00 UTC",
        "round_refs": [], "uuid": f"test-{event}",
    })
    path.write_text(json.dumps(kg, ensure_ascii=False), encoding="utf-8")


def test_retrieve_covers_interactions(tmp_env):
    """BC-003 回归：顶层 interactions 必须能被检索到。

    曾因 `_node_lists()` 只遍历 nodes 下三层，而 interactions 在 KG 顶层，
    47 条事件性记忆一条都召回不到——是死数据。
    """
    _add_interaction(tmp_env["kg_path"], "测试专属事件",
                     "独特触发词ZZQQ", "独特解决词JJXX")
    hits = _store(tmp_env).retrieve("独特触发词ZZQQ", limit=5)
    assert hits, "顶层 interactions 应能被检索到（BC-003）"
    assert any("测试专属事件" in (h.get("event_label") or "") for h in hits)


def test_retrieve_covers_interactions_resolution_field(tmp_env):
    """resolution 字段也要参与匹配——光匹配 event 会漏掉「怎么解决的」。"""
    _add_interaction(tmp_env["kg_path"], "某事件", "某触发", "独特解决词JJXX")
    hits = _store(tmp_env).retrieve("独特解决词JJXX", limit=5)
    assert hits, "interactions 的 resolution 字段应参与检索"


def test_retrieve_still_covers_dynamics_layers(tmp_env):
    """接入 interactions 不能挤掉原有三层——防「修一个坏一个」。"""
    store = _store(tmp_env)
    store.create(layer="Ego", event_label="原有节点标记PPKK",
                 description="d", evidence="e")
    hits = store.retrieve("原有节点标记PPKK", limit=5)
    assert any("原有节点标记PPKK" in (h.get("event_label") or "") for h in hits)
