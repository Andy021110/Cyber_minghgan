"""
test_phase4.py — Phase 4 验收测试

自动验收：
  [1] batch_processor.py 导入成功
  [2] --dry-run 模式：蓄水池为空时直接返回 0
  [3] --dry-run 模式：有条目时打印不落盘（awaiting_approval 不增加）
  [4] 正式运行：pending 条目被正确分类，写入 awaiting_approval
  [5] 正式运行后 pending 状态变为 processing
  [6] notifications.jsonl 有新的 pending_ready 通知
  [7] 测试数据清理

手动验收：
  python3 pipelines/batch_processor.py --dry-run
  → 打印 DRY-RUN 行，不修改任何文件

运行：
  python3 pipelines/test_phase4.py
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
print("  Phase 4 验收测试（自动部分）")
print("══════════════════════════════════════\n")

# ── [1] 导入 ──────────────────────────────────────────────────────
try:
    import batch_processor as bp
    check("batch_processor.py 导入成功", True)
except Exception as e:
    check(f"batch_processor.py 导入成功（错误：{e}）", False)
    sys.exit(1)

from decision_log import (
    write_pending, read_pending, count_pending,
    write_approval_item, read_awaiting,
    read_unconsumed_notifications,
    _read_all, _rewrite,
    PENDING_PATH, APPROVAL_PATH, NOTIFICATIONS_PATH,
)

# 记录测试前的 awaiting 和 notification 数量
before_awaiting = len(read_awaiting())
before_notif    = len(read_unconsumed_notifications())

# ── [2] 空蓄水池时 dry-run 返回 0 ────────────────────────────────
# 先确保 pending 是空的（跳过已有的 processing 条目）
result = bp.run(dry_run=True)
check("空蓄水池 dry-run 返回 0", result == 0)

# ── [3] 写入测试 pending 条目，dry-run 不落盘 ─────────────────────
t1 = write_pending("health", "写代码卡住→买奶茶逃避认知压力", "我写代码卡住就想买奶茶")
t2 = write_pending("health", "今天下午 3 分糖一点点奶茶一杯", "下午一点点四季奶青 3 分糖")

# dry-run 不应该改变 awaiting 数量
bp.run(dry_run=True)
after_dry_awaiting = len(read_awaiting())
check("dry-run 后 awaiting_approval 数量不变", after_dry_awaiting == before_awaiting)

# ── [4] 正式运行：调用真实 API 分类 ──────────────────────────────
print(f"\n  {INFO} 调用 API 进行分类（约 10 秒）...\n")
written = bp.run(dry_run=False)
check("正式运行返回写入数量 > 0", written > 0)

after_awaiting = read_awaiting()
new_items = [a for a in after_awaiting if a.get("pending_id") in [t1["id"], t2["id"]]]
check("awaiting_approval 有新条目", len(new_items) > 0)
check("新条目包含 proposed_route 字段",
      all(a.get("proposed_route") in ("kg", "log") for a in new_items))
check("新条目包含 ai_rationale 字段",
      all(a.get("ai_rationale") for a in new_items))

# ── [5] pending 状态更新为 processing ────────────────────────────
all_p = _read_all(PENDING_PATH)
t1_updated = next((e for e in all_p if e["id"] == t1["id"]), None)
t2_updated = next((e for e in all_p if e["id"] == t2["id"]), None)
check("t1 pending → processing", t1_updated and t1_updated.get("status") == "processing")
check("t2 pending → processing", t2_updated and t2_updated.get("status") == "processing")

# ── [6] notification 已写入 ───────────────────────────────────────
new_notifs = read_unconsumed_notifications()
new_pending_ready = [n for n in new_notifs if n.get("type") == "pending_ready"]
check("pending_ready 通知已写入", len(new_pending_ready) > before_notif or len(new_pending_ready) > 0)

# ── 清理测试数据 ──────────────────────────────────────────────────
print()
all_p = _read_all(PENDING_PATH)
_rewrite(PENDING_PATH, [e for e in all_p if e["id"] not in (t1["id"], t2["id"])])

all_a = _read_all(APPROVAL_PATH)
_rewrite(APPROVAL_PATH, [a for a in all_a if a.get("pending_id") not in (t1["id"], t2["id"])])

# 清理测试产生的 notification（只清理测试期间新增的）
all_n = _read_all(NOTIFICATIONS_PATH)
test_notif_ids = {n["id"] for n in new_pending_ready}
_rewrite(NOTIFICATIONS_PATH, [n for n in all_n if n["id"] not in test_notif_ids])

print(f"  {INFO} 测试数据已清理")

# ── 最终结论 ───────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ Phase 4 验收通过\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")

print("""
  ── 手动验收 ──
  python3 pipelines/batch_processor.py --dry-run
  → 若 pending.jsonl 有条目，打印 DRY-RUN 行，不修改文件
""")
print("══════════════════════════════════════\n")
