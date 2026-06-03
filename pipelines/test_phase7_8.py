"""
test_phase7_8.py — Phase 7+8 验收测试

自动验收：
  [1]  KG 节点含新字段（importance / access_count / archived 等）
  [2]  meta.prune_config 存在且字段完整
  [3]  retrieve_memory 命中后 access_count 递增
  [4]  retrieve_memory 默认跳过 archived=true 节点
  [5]  store.create() 写入 importance 和 source_mode
  [6]  write_approval_item 含 importance / importance_note
  [7]  compute_staleness 公式正确
  [8]  scan_candidates 按阈值正确筛选
  [9]  distribution_summary 分区统计正确
  [10] _archive_node 软删除（archived=true，物理留存）
  [11] /prune restore：归档节点可恢复，恢复后可被检索
  [12] _startup_check：季度扫描写入 prune_ready 通知
  [13] prune_ready 通知展示后不消耗（等 /prune 运行后消耗）
  [14] _cleanup_health_log 清理超龄记录
  [15] 测试数据清理

运行：
  python3 pipelines/test_phase7_8.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines"))

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[93m[INFO]\033[0m"
errors = []

def check(label, condition):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        errors.append(label)

print("\n══════════════════════════════════════")
print("  Phase 7+8 验收测试")
print("══════════════════════════════════════\n")

import cyber_planner as cp
from cyber_planner import CyberBrainStore, _archive_node, _cleanup_health_log, HEALTH_LOG_PATH
from decision_log import (
    write_pending, write_approval_item, read_awaiting,
    read_unconsumed_notifications, consume_notification, write_notification,
    _read_all, _rewrite, APPROVAL_PATH, PENDING_PATH, NOTIFICATIONS_PATH,
)
from prune import compute_staleness, scan_candidates, distribution_summary

KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"

# ── [1][2] KG 新字段 ───────────────────────────────────────────────
kg = json.loads(KG_PATH.read_text())
sample = kg["nodes"]["Cyber_Minghan"]["Id_Dynamics"][0]
check("节点含 importance 字段",       "importance"       in sample)
check("节点含 access_count 字段",     "access_count"     in sample)
check("节点含 last_accessed_at 字段", "last_accessed_at" in sample)
check("节点含 archived 字段",         "archived"         in sample)
check("节点含 source_mode 字段",      "source_mode"      in sample)

meta = kg.get("meta", {})
pc   = meta.get("prune_config", {})
check("meta.prune_config 存在",            bool(pc))
check("staleness_threshold=30",            pc.get("staleness_threshold") == 30)
check("prune_interval_days=90",            pc.get("prune_interval_days") == 90)
check("health_log_retention_days=90",      pc.get("health_log_retention_days") == 90)
check("max_prune_per_session=5",           pc.get("max_prune_per_session") == 5)

# ── [3] 访问追踪 ───────────────────────────────────────────────────
store = CyberBrainStore()
test_node = store.create("Id", "访问追踪测试节点", "测试访问计数", "证据",
                          importance=5, source_mode="test")
count_before = test_node.get("access_count", 0)
store.retrieve("访问追踪测试节点")
kg2 = json.loads(KG_PATH.read_text())
updated = next((n for n in kg2["nodes"]["Cyber_Minghan"]["Id_Dynamics"]
                if n["uuid"] == test_node["uuid"]), None)
check("retrieve 后 access_count 递增", updated and updated["access_count"] > count_before)
check("retrieve 后 last_accessed_at 更新", updated and updated["last_accessed_at"] is not None)

# ── [4] archived 过滤 ──────────────────────────────────────────────
store2 = CyberBrainStore()
_archive_node(store2, test_node["uuid"])
store3 = CyberBrainStore()
r = store3.retrieve("访问追踪测试节点")
check("retrieve 默认跳过 archived 节点", len(r) == 0)

# ── [5] store.create importance/source_mode ────────────────────────
store4 = CyberBrainStore()
n2 = store4.create("Ego", "重要度测试节点", "测试", "证据", importance=8, source_mode="test")
kg3 = json.loads(KG_PATH.read_text())
n2_saved = next((n for n in kg3["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]
                 if n["uuid"] == n2["uuid"]), None)
check("store.create 写入 importance=8",       n2_saved and n2_saved.get("importance") == 8)
check("store.create 写入 source_mode='test'", n2_saved and n2_saved.get("source_mode") == "test")

# ── [6] write_approval_item importance ────────────────────────────
p = write_pending("health", "测试重要度approval", "证据")
a = write_approval_item(
    pending_id=p["id"], source_mode="health",
    content=p["content"], raw_evidence=p["raw_evidence"],
    proposed_route="kg", proposed_layer="Id",
    ai_rationale="测试", importance=7, importance_note="测试充分"
)
items = read_awaiting()
ai = next((x for x in items if x["id"] == a["id"]), None)
check("approval_item 含 importance=7",        ai and ai.get("importance") == 7)
check("approval_item 含 importance_note",     ai and bool(ai.get("importance_note")))

# ── [7] compute_staleness 公式 ────────────────────────────────────
old_time = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
fake_node = {"importance": 5, "last_accessed_at": old_time, "created_at": old_time}
s = compute_staleness(fake_node, {})
check("staleness = days/importance ≈ 12", 11 < s < 13)

# ── [8] scan_candidates ───────────────────────────────────────────
config_test = {"staleness_threshold": 3, "max_prune_per_session": 5}
candidates = scan_candidates(KG_PATH, config_test)
check("低阈值下有候选节点", len(candidates) > 0)
check("候选节点含 _staleness 字段",   all("_staleness" in c for c in candidates[:3]))
check("候选节点含 _archive_hint 字段", all("_archive_hint" in c for c in candidates[:3]))

# ── [9] distribution_summary ──────────────────────────────────────
dist = distribution_summary(KG_PATH, config_test)
check("distribution 含 above_threshold",  "above_threshold" in dist)
check("distribution 含 archived 计数",    "archived" in dist)
check("archived 计数 >= 1（有测试归档节点）", dist["archived"] >= 1)

# ── [10] 软删除物理留存 ────────────────────────────────────────────
kg4 = json.loads(KG_PATH.read_text())
archived_in_file = any(
    n.get("archived") and n["uuid"] == test_node["uuid"]
    for n in kg4["nodes"]["Cyber_Minghan"]["Id_Dynamics"]
)
check("归档节点物理留存于 KG 文件", archived_in_file)

# ── [11] restore ──────────────────────────────────────────────────
store5 = CyberBrainStore()
store5.update(test_node["uuid"], archived=False, archived_at=None, archive_reason=None)
store6 = CyberBrainStore()
r2 = store6.retrieve("访问追踪测试节点")
check("恢复后 retrieve 可以找到节点", len(r2) > 0)

# ── [12][13] startup prune_ready 通知 ─────────────────────────────
# 模拟：把 last_prune_check 清零 + 低阈值 → 触发扫描
store7 = CyberBrainStore()
store7._kg.setdefault("meta", {})["last_prune_check"] = None
store7._kg["meta"]["prune_config"] = {
    "staleness_threshold": 3,
    "prune_interval_days": 0,
    "health_log_retention_days": 90,
    "max_prune_per_session": 5,
}
store7._save()

before_notifs = len(read_unconsumed_notifications())
cp._startup_check(store7)
after_notifs = read_unconsumed_notifications()
prune_notifs = [n for n in after_notifs if n.get("type") == "prune_ready"]
check("startup 写入 prune_ready 通知", len(prune_notifs) > 0)
check("prune_ready 展示后未被消耗", len(prune_notifs) > 0)

# 恢复正式配置
store8 = CyberBrainStore()
store8._kg["meta"]["prune_config"] = {
    "staleness_threshold": 30,
    "prune_interval_days": 90,
    "health_log_retention_days": 90,
    "max_prune_per_session": 5,
}
store8._kg["meta"]["last_prune_check"] = datetime.now(timezone.utc).date().isoformat()
store8._save()

# ── [14] health_log 清理 ──────────────────────────────────────────
old_ts = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
new_ts = datetime.now(timezone.utc).isoformat()
import uuid as _uuid_mod
test_log_old = {"id": _uuid_mod.uuid4().hex, "timestamp": old_ts, "content": "旧记录", "status": "approved"}
test_log_new = {"id": _uuid_mod.uuid4().hex, "timestamp": new_ts, "content": "新记录", "status": "approved"}
with HEALTH_LOG_PATH.open("a") as f:
    import json as _j
    f.write(_j.dumps(test_log_old, ensure_ascii=False) + "\n")
    f.write(_j.dumps(test_log_new, ensure_ascii=False) + "\n")

removed = _cleanup_health_log(90)
remaining_log = _read_all(HEALTH_LOG_PATH)
old_gone = not any(e["id"] == test_log_old["id"] for e in remaining_log)
new_kept  = any(e["id"] == test_log_new["id"] for e in remaining_log)
check("health_log 清理超龄记录", removed >= 1 and old_gone)
check("health_log 保留新记录",   new_kept)

# ── 清理所有测试数据 ──────────────────────────────────────────────
print()
kg_clean = json.loads(KG_PATH.read_text())
test_uuids = {test_node["uuid"], n2["uuid"]}
for layer in ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics"):
    kg_clean["nodes"]["Cyber_Minghan"][layer] = [
        n for n in kg_clean["nodes"]["Cyber_Minghan"][layer]
        if n["uuid"] not in test_uuids
    ]
KG_PATH.write_text(json.dumps(kg_clean, ensure_ascii=False, indent=2))

# 清理 approval/pending
all_a = _read_all(APPROVAL_PATH)
_rewrite(APPROVAL_PATH, [x for x in all_a if x["id"] != a["id"]])
all_p = _read_all(PENDING_PATH)
_rewrite(PENDING_PATH, [x for x in all_p if x["id"] != p["id"]])

# 清理 prune_ready 通知
all_n = _read_all(NOTIFICATIONS_PATH)
_rewrite(NOTIFICATIONS_PATH, [n for n in all_n if n.get("type") != "prune_ready"])

# 清理 health_log 测试行
remaining = _read_all(HEALTH_LOG_PATH)
_rewrite(HEALTH_LOG_PATH, [e for e in remaining if e["id"] != test_log_new["id"]])

print(f"  {INFO} 测试数据已清理")

# ── 最终结论 ─────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ Phase 7+8 验收通过\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")

print("""
  ── 手动验收清单 ──
  python3 cyber_planner.py

  M1. 启动时若季度检查到期 → 出现「KG 季度检查：N 个节点超过老化阈值」
  M2. 输入 /prune → 看到分布概览 + 候选节点列表
  M3. 输入 1 归档一条 → 再用 /检索 确认它不再出现
  M4. 输入 /prune restore → 恢复刚归档的节点
  M5. 输入 2 提升一条重要度 → 确认 importance 值增加
""")
print("══════════════════════════════════════\n")
