"""
test_phase1.py — Phase 1 验收测试

验收通过标准：
  [1] 能写入一条 pending 条目，字段完整
  [2] 能按 status 过滤读取
  [3] 能更新 status
  [4] 能写入并读取 notification
  [5] notification 消费后不再出现在未读列表
  [6] 测试结束后自动清理写入的测试数据

运行：
  python3 pipelines/test_phase1.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipelines"))

from decision_log import (
    write_pending, read_pending, count_pending, update_pending_status,
    write_notification, read_unconsumed_notifications, consume_notification,
    PENDING_PATH, NOTIFICATIONS_PATH,
)

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"

errors = []

def check(label: str, condition: bool):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        errors.append(label)


print("\n══════════════════════════════")
print("  Phase 1 验收测试")
print("══════════════════════════════\n")

# ── 测试 1：写入 pending 条目 ──────────────────────────────────────
entry = write_pending(
    source_mode="health",
    content="高压写代码结束后产生强烈炸鸡渴望",
    raw_evidence="用户说：今天加班到11点，现在脑子转不动了，好想吃炸鸡",
    trigger_context="用户刚聊完工作压力后切换至健康模式",
)

check("返回值包含 id 字段",       bool(entry.get("id")))
check("返回值包含 timestamp",     bool(entry.get("timestamp")))
check("status 默认为 pending",    entry.get("status") == "pending")
check("proposed_route 默认为 None", entry.get("proposed_route") is None)
check("proposed_layer 默认为 None", entry.get("proposed_layer") is None)
check("source_mode 正确写入",     entry.get("source_mode") == "health")

# ── 测试 2：读取与过滤 ─────────────────────────────────────────────
pending_list = read_pending(status="pending")
check("能读取到刚写入的条目",      any(e["id"] == entry["id"] for e in pending_list))
check("count_pending 返回正整数", count_pending("pending") >= 1)

empty = read_pending(status="processing")
check("过滤 processing 返回空列表（或不含测试条目）",
      not any(e["id"] == entry["id"] for e in empty))

# ── 测试 3：更新 status ────────────────────────────────────────────
ok = update_pending_status(entry["id"], "processing",
                           proposed_route="kg", proposed_layer="Id")
check("update_pending_status 返回 True",  ok)

updated = next((e for e in read_pending(status=None) if e["id"] == entry["id"]), None)
check("status 已更新为 processing",       updated and updated["status"] == "processing")
check("proposed_route 已写入",            updated and updated.get("proposed_route") == "kg")
check("proposed_layer 已写入",            updated and updated.get("proposed_layer") == "Id")

# ── 测试 4：写入 notification ──────────────────────────────────────
notif = write_notification("pending_ready", "有 1 条待审批，输入 /review 查看")
check("notification 写入成功",        bool(notif.get("id")))
check("consumed 默认为 False",        notif.get("consumed") is False)

unconsumed = read_unconsumed_notifications()
check("未消费通知列表包含刚写入的条目",
      any(n["id"] == notif["id"] for n in unconsumed))

# ── 测试 5：消费 notification ──────────────────────────────────────
consume_ok = consume_notification(notif["id"])
check("consume_notification 返回 True", consume_ok)

unconsumed_after = read_unconsumed_notifications()
check("消费后不再出现在未读列表",
      not any(n["id"] == notif["id"] for n in unconsumed_after))

# ── 清理测试数据 ───────────────────────────────────────────────────
print()

from decision_log import _read_all, _rewrite

# 清理 pending
all_p = _read_all(PENDING_PATH)
cleaned_p = [e for e in all_p if e.get("id") != entry["id"]]
_rewrite(PENDING_PATH, cleaned_p)

# 清理 notifications
all_n = _read_all(NOTIFICATIONS_PATH)
cleaned_n = [e for e in all_n if e.get("id") != notif["id"]]
_rewrite(NOTIFICATIONS_PATH, cleaned_n)

print("  [清理] 测试数据已移除\n")

# ── 最终结论 ───────────────────────────────────────────────────────
print("══════════════════════════════")
if not errors:
    print("  \033[92m✓ Phase 1 验收通过（全部检查项通过）\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════\n")
