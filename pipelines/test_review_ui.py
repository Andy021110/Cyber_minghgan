"""
test_review_ui.py — /review 两步决策流程验收（A1 + A2）

测试场景：
  [1]  Y → 回车接受 importance → 回车保留描述 → 写入 KG
  [2]  Y → 覆盖 importance=3 → 输入新描述 → 写入 KG，描述被替换
  [3]  Y → log 路由 → 直接写入 health_log（无 importance/描述步骤）
  [4]  N → 输入理由 → 拒绝并归档
  [5]  N → 回车跳过理由 → 拒绝无理由
  [6]  s → 条目保持 awaiting，不被消耗
  [7]  q → 循环中断，显示剩余数
  [8]  非法输入（随便说） → 重新提示，不崩溃
  [9]  /review 完成摘要含 skipped 计数

运行：
  python3 pipelines/test_review_ui.py
"""

import sys, json, uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines"))

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
errors = []

def check(label, condition):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        errors.append(label)

print("\n══════════════════════════════════════")
print("  /review UI 验收（A1 + A2）")
print("══════════════════════════════════════\n")

import cyber_planner as cp
from cyber_planner import CyberBrainStore, _review_ask_decision
from decision_log import (
    write_approval_item, write_pending, read_awaiting,
    _read_all, _rewrite, APPROVAL_PATH, PENDING_PATH,
)

HEALTH_LOG_PATH = ROOT / "decision_logs" / "health_log.jsonl"

KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"

# ── 全局清理：消除上次测试遗留 ───────────────────────────────────
def _clear_test_queue():
    """清理测试条目，避免跨场景/跨次运行污染。"""
    all_a = _read_all(APPROVAL_PATH)
    _rewrite(APPROVAL_PATH, [x for x in all_a if x.get("source_mode") != "test"])
    all_p = _read_all(PENDING_PATH)
    _rewrite(PENDING_PATH, [x for x in all_p if x.get("source_mode") != "test"])

_clear_test_queue()  # 启动时先清理上次遗留

# ── 工具：写入测试 approval 条目 ──────────────────────────────────
def _make_approval(route="kg", layer="Id", importance=6, imp_note="测试"):
    p = write_pending("test", f"测试观察_{uuid.uuid4().hex[:4]}", "测试证据")
    a = write_approval_item(
        pending_id=p["id"], source_mode="test",
        content=p["content"], raw_evidence=p["raw_evidence"],
        proposed_route=route, proposed_layer=layer if route=="kg" else None,
        ai_rationale="测试分类",
        importance=importance if route=="kg" else None,
        importance_note=imp_note if route=="kg" else None,
    )
    return p, a

def _clear_test_queue():
    """清理上一个场景遗留的测试条目，避免跨场景污染。"""
    all_a = _read_all(APPROVAL_PATH)
    _rewrite(APPROVAL_PATH, [x for x in all_a if x.get("source_mode") != "test"])
    all_p = _read_all(PENDING_PATH)
    _rewrite(PENDING_PATH, [x for x in all_p if x.get("source_mode") != "test"])

# ── [8] 非法输入重新提示 ───────────────────────────────────────────
print("[场景8] 非法输入重新提示")
with patch("builtins.input", side_effect=["随便说", "什么", "y"]):
    result = _review_ask_decision()
check("非法输入后最终返回 y", result == "y")

# ── [1] Y → 回车接受 importance → 回车保留描述 → 写入 KG ──────────
print("\n[场景1] Y + 回车接受 importance + 回车保留描述")
p1, a1 = _make_approval(route="kg", layer="Id", importance=6)
store = CyberBrainStore()
kg_before = sum(len(store._kg["nodes"]["Cyber_Minghan"][l])
                for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))

with patch("builtins.input", side_effect=["y", "", ""]):  # Y, imp回车, desc回车
    cp.handle_review(store)

store2 = CyberBrainStore()
kg_after = sum(len(store2._kg["nodes"]["Cyber_Minghan"][l])
               for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))
new_nodes = [n for n in store2._kg["nodes"]["Cyber_Minghan"]["Id_Dynamics"]
             if n.get("source_mode") == "test"]
check("KG 节点数 +1", kg_after == kg_before + 1)
check("importance 保留 AI 建议值 6", new_nodes and new_nodes[-1]["importance"] == 6)
check("描述保留原始内容", new_nodes and new_nodes[-1]["description"] == a1["content"])

# ── [2] Y → 覆盖 importance=3 → 输入新描述 ────────────────────────
print("\n[场景2] Y + 覆盖 importance=3 + 输入新描述")
p2, a2 = _make_approval(route="kg", layer="Ego", importance=7)
store3 = CyberBrainStore()

with patch("builtins.input", side_effect=["y", "3", "这是新的描述内容"]):
    cp.handle_review(store3)

store4 = CyberBrainStore()
ego_nodes = [n for n in store4._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]
             if n.get("source_mode") == "test"]
check("importance 被覆盖为 3", ego_nodes and ego_nodes[-1]["importance"] == 3)
check("描述被替换为新内容", ego_nodes and ego_nodes[-1]["description"] == "这是新的描述内容")

# ── [3] Y → log 路由 → 写入 health_log ───────────────────────────
print("\n[场景3] Y + log 路由")
p3, a3 = _make_approval(route="log")
store5 = CyberBrainStore()
log_before = len(_read_all(HEALTH_LOG_PATH))

with patch("builtins.input", side_effect=["y"]):
    cp.handle_review(store5)

log_after = _read_all(HEALTH_LOG_PATH)
check("health_log 新增 1 条", len(log_after) == log_before + 1)
check("health_log 状态为 approved", log_after[-1].get("status") == "approved")

# ── [4] N → 输入理由 ─────────────────────────────────────────────
print("\n[场景4] N + 输入理由")
p4, a4 = _make_approval(route="kg", layer="Id")
store6 = CyberBrainStore()
log_before2 = len(_read_all(HEALTH_LOG_PATH))

with patch("builtins.input", side_effect=["n", "理由测试"]):
    cp.handle_review(store6)

log_after2 = _read_all(HEALTH_LOG_PATH)
check("health_log 新增 rejected 条目", len(log_after2) == log_before2 + 1)
check("rejected_reason 已记录", log_after2[-1].get("rejected_reason") == "理由测试")

# ── [5] N → 回车跳过理由 ─────────────────────────────────────────
print("\n[场景5] N + 回车不输理由")
p5, a5 = _make_approval(route="kg", layer="Id")
store7 = CyberBrainStore()

with patch("builtins.input", side_effect=["n", ""]):
    cp.handle_review(store7)

log_after3 = _read_all(HEALTH_LOG_PATH)
check("拒绝无理由时 rejected_reason 为空", log_after3[-1].get("rejected_reason") == "")

# ── [6] s → 条目保持 awaiting ────────────────────────────────────
print("\n[场景6] s → 跳过，条目保持 awaiting")
_clear_test_queue()
p6, a6 = _make_approval(route="kg", layer="Id")
store8 = CyberBrainStore()

with patch("builtins.input", side_effect=["s"]):
    cp.handle_review(store8)

awaiting_after = read_awaiting()
still_there = any(x["id"] == a6["id"] for x in awaiting_after)
check("跳过后条目仍在 awaiting 队列", still_there)

# ── [7] q → 中断并显示剩余数 ────────────────────────────────────
print("\n[场景7] q → 暂停审批")
_clear_test_queue()
p7a, a7a = _make_approval(route="kg", layer="Id")
p7b, a7b = _make_approval(route="kg", layer="Id")
store9 = CyberBrainStore()

output_lines = []
original_print = print
def capture_print(*args, **kwargs):
    line = " ".join(str(a) for a in args)
    output_lines.append(line)
    original_print(*args, **kwargs)

import builtins
builtins.print = capture_print
with patch("builtins.input", side_effect=["q"]):
    cp.handle_review(store9)
builtins.print = original_print

check("q 暂停时输出剩余条数", any("剩余" in l for l in output_lines))

# ── [9] 完成摘要含 skipped ───────────────────────────────────────
print("\n[场景9] 完成摘要含 skipped 计数")
_clear_test_queue()
p9, a9 = _make_approval(route="kg", layer="Id")
store10 = CyberBrainStore()
summary_lines = []
builtins.print = capture_print
output_lines.clear()
with patch("builtins.input", side_effect=["s"]):
    cp.handle_review(store10)
builtins.print = original_print
check("完成摘要包含跳过计数", any("跳过" in l for l in output_lines))

# ── 清理测试数据 ──────────────────────────────────────────────────
print()
kg_clean = json.loads(KG_PATH.read_text())
for layer in ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics"):
    kg_clean["nodes"]["Cyber_Minghan"][layer] = [
        n for n in kg_clean["nodes"]["Cyber_Minghan"][layer]
        if n.get("source_mode") != "test"
    ]
KG_PATH.write_text(json.dumps(kg_clean, ensure_ascii=False, indent=2))

all_a = _read_all(APPROVAL_PATH)
_rewrite(APPROVAL_PATH, [x for x in all_a if x.get("source_mode") != "test"])
all_p = _read_all(PENDING_PATH)
_rewrite(PENDING_PATH, [x for x in all_p if x.get("source_mode") != "test"])
log_all = _read_all(HEALTH_LOG_PATH)
_rewrite(HEALTH_LOG_PATH, [x for x in log_all if x.get("source_mode") != "test"])

print("  \033[93m[INFO]\033[0m 测试数据已清理")

# ── 结论 ──────────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ /review UI 验收通过（A1 + A2）\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════════════\n")
