"""
test_phase5.py — Phase 5+6 验收测试

自动验收：
  [1] cyber_planner 导入成功（含新函数）
  [2] handle_review 函数存在
  [3] _startup_check 函数存在
  [4] /review 在代码中出现在 handle_admin_command 之前
  [5] BATCH_THRESHOLD 常量存在且 > 0
  [6] HEALTH_LOG_PATH 指向 decision_logs/health_log.jsonl
  [7] approved_kg：KG 中写入新节点，uuid 可查
  [8] approved_log：health_log.jsonl 有新行
  [9] rejected：health_log.jsonl 有 rejected_reason 字段
  [10] awaiting_approval 状态变为 approved_kg / approved_log / rejected
  [11] pending 状态变为 approved / rejected
  [12] 测试数据清理

手动验收：
  python3 cyber_planner.py
  → 启动时若有未读通知，打印并消耗
  → 输入 /review，走一遍完整审批流程

运行：
  python3 pipelines/test_phase5.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines"))

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[93m[INFO]\033[0m"
errors = []

def check(label: str, condition: bool):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        errors.append(label)

print("\n══════════════════════════════════════")
print("  Phase 5+6 验收测试（自动部分）")
print("══════════════════════════════════════\n")

# ── [1] 导入 ──────────────────────────────────────────────────────
try:
    import cyber_planner as cp
    check("cyber_planner.py 导入成功", True)
except Exception as e:
    check(f"cyber_planner.py 导入成功（错误：{e}）", False)
    sys.exit(1)

# ── [2][3][4][5][6] 结构检查 ──────────────────────────────────────
check("handle_review 函数存在",    hasattr(cp, "handle_review"))
check("_startup_check 函数存在",   hasattr(cp, "_startup_check"))
check("BATCH_THRESHOLD 存在且 > 0", getattr(cp, "BATCH_THRESHOLD", 0) > 0)
check("HEALTH_LOG_PATH 路径正确",
      str(getattr(cp, "HEALTH_LOG_PATH", "")).endswith("decision_logs/health_log.jsonl"))

src = Path(ROOT / "cyber_planner.py").read_text()
review_pos = src.find("/review")
admin_pos  = src.find("handle_admin_command(")
check("/review 拦截在 handle_admin_command 之前", 0 < review_pos < admin_pos)

# ── 准备测试数据 ───────────────────────────────────────────────────
from decision_log import (
    APPROVAL_PATH,
    PENDING_PATH,
    _read_all,
    _rewrite,
    write_approval_item,
    write_pending,
)

from cyber_planner import HEALTH_LOG_PATH, CyberBrainStore

store = CyberBrainStore()

# 读取当前 KG 节点数
def kg_id_count():
    kg = json.loads(Path(ROOT / "yuanbao_cyber_minghan_kg.json").read_text(encoding="utf-8"))
    return len(kg["nodes"]["Cyber_Minghan"].get("Id_Dynamics", []))

before_kg_count = kg_id_count()
before_log_lines = len(_read_all(HEALTH_LOG_PATH)) if HEALTH_LOG_PATH.exists() else 0

# 写入 3 条测试 pending
p_kg  = write_pending("health", "高压写代码时逃跑冲动被奶茶激活", "我写代码卡住就想买奶茶")
p_log = write_pending("health", "今天下午3分糖一点点奶茶一杯",   "下午一点点四季奶青3分糖")
p_rej = write_pending("health", "偶尔想吃薯片",                   "吃了一包薯片")

# 直接写入 awaiting_approval（跳过 API，模拟批处理已完成）
a_kg = write_approval_item(
    pending_id=p_kg["id"],
    source_mode="health",
    content=p_kg["content"],
    raw_evidence=p_kg["raw_evidence"],
    proposed_route="kg",
    proposed_layer="Id",
    ai_rationale="逃避冲动，具有稳定触发→反应结构",
)
a_log = write_approval_item(
    pending_id=p_log["id"],
    source_mode="health",
    content=p_log["content"],
    raw_evidence=p_log["raw_evidence"],
    proposed_route="log",
    proposed_layer=None,
    ai_rationale="具体饮食决策，单次记录",
)
a_rej = write_approval_item(
    pending_id=p_rej["id"],
    source_mode="health",
    content=p_rej["content"],
    raw_evidence=p_rej["raw_evidence"],
    proposed_route="log",
    proposed_layer=None,
    ai_rationale="单次零食行为",
)

print(f"\n  {INFO} 测试数据已写入，开始模拟审批...\n")

# ── [7][8][9] 模拟 handle_review 核心逻辑 ─────────────────────────
# 直接调用各写入路径，不需要交互式 input()

from datetime import datetime, timezone

from decision_log import resolve_approval, update_pending_status

from cyber_planner import _uuid, _write_health_log_entry

ts = datetime.now(timezone.utc).isoformat()

# Case A: approved_kg（Id 层）
new_node = store.create(
    layer="Id",
    event_label=a_kg["content"][:40],
    description=a_kg["content"],
    evidence=a_kg["raw_evidence"],
    batch_id="TestReview",
)
resolve_approval(a_kg["id"], "approved_kg", "")
update_pending_status(p_kg["id"], "approved")
check("approved_kg：KG 中新增 Id 节点", kg_id_count() > before_kg_count)
check("新节点含 batch_id=TestReview",
      new_node.get("batch_id") == "TestReview")

# Case B: approved_log
_write_health_log_entry({
    "id":           _uuid.uuid4().hex,
    "timestamp":    ts,
    "source_mode":  "health",
    "content":      a_log["content"],
    "raw_evidence": a_log["raw_evidence"],
    "review_id":    a_log["id"],
    "status":       "approved",
})
resolve_approval(a_log["id"], "approved_log", "")
update_pending_status(p_log["id"], "approved")
after_log_lines = len(_read_all(HEALTH_LOG_PATH))
check("approved_log：health_log.jsonl 有新行", after_log_lines > before_log_lines)

# Case C: rejected
_write_health_log_entry({
    "id":              _uuid.uuid4().hex,
    "timestamp":       ts,
    "source_mode":     "health",
    "content":         a_rej["content"],
    "raw_evidence":    a_rej["raw_evidence"],
    "review_id":       a_rej["id"],
    "status":          "rejected",
    "rejected_reason": "偶发例外，不记录",
})
resolve_approval(a_rej["id"], "rejected", "偶发例外，不记录")
update_pending_status(p_rej["id"], "rejected")

# 读取 health_log，确认 rejected_reason 存在
log_entries = _read_all(HEALTH_LOG_PATH)
rej_entries = [e for e in log_entries if e.get("status") == "rejected" and e.get("review_id") == a_rej["id"]]
check("rejected：health_log 有 rejected_reason 字段",
      len(rej_entries) > 0 and rej_entries[0].get("rejected_reason") == "偶发例外，不记录")

# ── [10][11] 状态检查 ─────────────────────────────────────────────
all_a = _read_all(APPROVAL_PATH)
a_kg_up  = next((e for e in all_a if e["id"] == a_kg["id"]),  None)
a_log_up = next((e for e in all_a if e["id"] == a_log["id"]), None)
a_rej_up = next((e for e in all_a if e["id"] == a_rej["id"]), None)
check("awaiting_approval kg → approved_kg",   a_kg_up  and a_kg_up.get("status")  == "approved_kg")
check("awaiting_approval log → approved_log", a_log_up and a_log_up.get("status") == "approved_log")
check("awaiting_approval rej → rejected",     a_rej_up and a_rej_up.get("status") == "rejected")

all_p = _read_all(PENDING_PATH)
p_kg_up  = next((e for e in all_p if e["id"] == p_kg["id"]),  None)
p_log_up = next((e for e in all_p if e["id"] == p_log["id"]), None)
p_rej_up = next((e for e in all_p if e["id"] == p_rej["id"]), None)
check("pending kg → approved",  p_kg_up  and p_kg_up.get("status")  == "approved")
check("pending log → approved", p_log_up and p_log_up.get("status") == "approved")
check("pending rej → rejected", p_rej_up and p_rej_up.get("status") == "rejected")

# ── 清理测试数据 ──────────────────────────────────────────────────
print()
# 删除 KG 测试节点
try:
    store.delete(new_node["uuid"])
    print(f"  {INFO} KG 测试节点已删除")
except Exception as e:
    print(f"  {INFO} KG 节点清理警告：{e}")

# 清理 pending
all_p = _read_all(PENDING_PATH)
test_ids = {p_kg["id"], p_log["id"], p_rej["id"]}
_rewrite(PENDING_PATH, [e for e in all_p if e["id"] not in test_ids])

# 清理 awaiting_approval
all_a = _read_all(APPROVAL_PATH)
test_a_ids = {a_kg["id"], a_log["id"], a_rej["id"]}
_rewrite(APPROVAL_PATH, [e for e in all_a if e["id"] not in test_a_ids])

# 清理 health_log 测试行
log_entries = _read_all(HEALTH_LOG_PATH)
test_review_ids = {a_kg["id"], a_log["id"], a_rej["id"]}
_rewrite(HEALTH_LOG_PATH, [e for e in log_entries if e.get("review_id") not in test_review_ids])

print(f"  {INFO} 测试数据已清理")

# ── 最终结论 ───────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ Phase 5+6 验收通过\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")

print("""
  ── 手动验收清单 ──
  python3 cyber_planner.py

  M1. 启动时若 decision_logs/ 有未读通知 → 打印并消耗
  M2. 用 health_coach 产生几条 pending → 运行 batch_processor
      → 再启动 cyber_planner，确认提醒「有N条待审批」
  M3. 输入 /review
      → 逐条显示内容、证据、AI 分类
  M4. 输入 Y → 采纳（AI 描述）
  M5. 输入 Y 我重写的描述 → 采纳（用户描述覆盖）
  M6. 输入 N 不够稳定 → 拒绝，确认 health_log.jsonl 有 rejected_reason
  M7. 被采纳的 KG 条目：cat yuanbao_cyber_minghan_kg.json 确认新节点存在
""")
print("══════════════════════════════════════\n")
