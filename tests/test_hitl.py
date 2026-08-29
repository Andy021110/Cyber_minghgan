"""HITL 写入纪律测试：pending 蓄水池 + awaiting 审批池 + 审批三档。

注意：函数通过模块属性访问（import pipelines.decision_log as dl），
确保 hitl_env 的 monkeypatch（logs_dir 隔离）生效，绝不写真实数据。
"""
import pipelines.decision_log as dl
from cyber_planner import CyberBrainStore, process_review_decision


# ── 蓄水池：pending 生命周期 ──────────────────────────────────

def test_write_and_read_pending(hitl_env):
    dl.write_pending("health", "用户最近在准备秋招", "evidence-1", "trigger-ctx")
    items = dl.read_pending(status="pending")
    assert len(items) == 1
    assert items[0]["content"] == "用户最近在准备秋招"
    assert items[0]["status"] == "pending"


def test_update_pending_status(hitl_env):
    entry = dl.write_pending("health", "内容", "ev")
    assert dl.update_pending_status(entry["id"], "approved") is True
    assert dl.read_pending(status="pending") == []
    assert len(dl.read_pending(status="approved")) == 1


def test_count_pending(hitl_env):
    dl.write_pending("health", "a", "ev")
    dl.write_pending("skill", "b", "ev")
    assert dl.count_pending() == 2


# ── 审批池：awaiting 生命周期（正确链路：批处理 → write_approval_item）──

def test_write_approval_and_read_awaiting(hitl_env):
    dl.write_approval_item("p1", "health", "深度工作偏好", "ev",
                           proposed_route="KG", proposed_layer="Ego",
                           ai_rationale="高置信")
    awaiting = dl.read_awaiting()
    assert len(awaiting) == 1
    assert awaiting[0]["status"] == "awaiting"
    assert awaiting[0]["proposed_layer"] == "Ego"


def test_resolve_approval(hitl_env):
    dl.write_approval_item("p1", "health", "内容", "ev",
                           proposed_route="KG", proposed_layer="Ego", ai_rationale="r")
    item = dl.read_awaiting()[0]
    assert dl.resolve_approval(item["id"], "rejected", "没依据") is True
    assert dl.read_awaiting() == []  # 处理完不在审批池


# ── 审批决策三档（process_review_decision，纯函数无 I/O 副作用）──

def _make_awaiting(hitl_env):
    dl.write_approval_item("p-test", "health", "深度工作偏好：早上写代码", "ev-1",
                           proposed_route="KG", proposed_layer="Ego", ai_rationale="r")
    return dl.read_awaiting()[0]


def test_rejected_records_reason(hitl_env):
    item = _make_awaiting(hitl_env)
    result = process_review_decision(None, item["id"], "rejected", user_note="没有依据")
    assert result["success"] is True
    assert dl.read_awaiting() == []


def test_approved_kg_writes_to_store(hitl_env, tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    item = _make_awaiting(hitl_env)
    result = process_review_decision(store, item["id"], "approved_kg",
                                     importance=7, visibility="private")
    assert result["success"] is True
    hits = store.retrieve("深度工作", limit=5)
    assert any("深度工作" in (h.get("event_label") or "") for h in hits)


def test_approved_log_not_in_kg(hitl_env, tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    before = len(store.retrieve("低置信度", limit=50))
    dl.write_approval_item("p-log", "health", "低置信度信息：随口一说", "ev",
                           proposed_route="LOG", proposed_layer="Ego", ai_rationale="低置信")
    item = dl.read_awaiting()[0]
    result = process_review_decision(store, item["id"], "approved_log")
    assert result["success"] is True
    hits = store.retrieve("低置信度", limit=50)
    assert len(hits) == before  # 只记日志不进图谱
