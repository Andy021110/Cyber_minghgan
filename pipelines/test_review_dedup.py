"""
test_review_dedup.py — /review 重复检测接入验收（C2）

测试场景：
  [1]  有相似节点时展示提示，选择追加证据 → 已有节点 importance+1，evidence 追加
  [2]  有相似节点时选择新建（n） → 正常写入新节点
  [3]  无 client 时跳过检测 → 正常走原有流程
  [4]  有相似节点选 i（忽略）→ 正常新建

运行：
  python3 pipelines/test_review_dedup.py
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines"))
load_dotenv(ROOT / ".env")

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
print("  /review 重复检测验收（C2）")
print("══════════════════════════════════════\n")

import anthropic
from decision_log import (
    APPROVAL_PATH,
    PENDING_PATH,
    _read_all,
    _rewrite,
    write_approval_item,
    write_pending,
)

from cyber_planner import CyberBrainStore, handle_review

KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"

def _clear_test_queue():
    all_a = _read_all(APPROVAL_PATH)
    _rewrite(APPROVAL_PATH, [x for x in all_a if x.get("source_mode") != "test"])
    all_p = _read_all(PENDING_PATH)
    _rewrite(PENDING_PATH, [x for x in all_p if x.get("source_mode") != "test"])

def _make_kg_approval(content):
    p = write_pending("test", content, "测试证据原文")
    a = write_approval_item(
        pending_id=p["id"], source_mode="test",
        content=content, raw_evidence="测试证据原文",
        proposed_route="kg", proposed_layer="Id",
        ai_rationale="测试分类", importance=5, importance_note="测试",
    )
    return p, a

_clear_test_queue()

# ── [1] 追加证据路径 ──────────────────────────────────────────────
print("[场景1] 相似节点 → 选择追加证据")
store = CyberBrainStore()
existing = store.create("Id", "工作卡住时买奶茶逃避压力",
                        "压力逃避描述", "原始证据",
                        importance=5, source_mode="test")
store2 = CyberBrainStore()
imp_before = existing["importance"]

p1, a1 = _make_kg_approval("项目遇到困难，忍不住去买了一杯奶茶")
store3 = CyberBrainStore()

# mock find_similar_nodes 返回已有节点
mock_similar = [dict(existing, _similarity_reason="同一压力→消费模式")]
client = anthropic.Anthropic()
kg_count_before = sum(len(store3._kg["nodes"]["Cyber_Minghan"][l])
                      for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))

with patch("cyber_planner.find_similar_nodes", return_value=mock_similar), \
     patch("builtins.input", side_effect=["y", "1"]):
    handle_review(store3, client)

store4 = CyberBrainStore()
updated = next((n for n in store4._kg["nodes"]["Cyber_Minghan"]["Id_Dynamics"]
                if n["uuid"] == existing["uuid"]), None)
kg_count_after = sum(len(store4._kg["nodes"]["Cyber_Minghan"][l])
                     for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))

check("追加证据后 importance +1",     updated and updated["importance"] == imp_before + 1)
check("追加证据后 evidence 含新内容", updated and "测试证据原文" in (updated.get("evidence") or ""))
check("追加证据不新建节点（总数不变）", kg_count_after == kg_count_before)

# ── [2] 有相似节点时选 n → 新建 ──────────────────────────────────
print("\n[场景2] 相似节点 → 选择新建（n）")
_clear_test_queue()
p2, a2 = _make_kg_approval("压力大时习惯性买甜食")
store5 = CyberBrainStore()
kg_before2 = sum(len(store5._kg["nodes"]["Cyber_Minghan"][l])
                 for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))

with patch("cyber_planner.find_similar_nodes", return_value=mock_similar), \
     patch("builtins.input", side_effect=["y", "n", "", ""]):
    handle_review(store5, client)

store6 = CyberBrainStore()
kg_after2 = sum(len(store6._kg["nodes"]["Cyber_Minghan"][l])
                for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))
check("选 n 时新建节点（总数+1）", kg_after2 == kg_before2 + 1)

# ── [3] client=None 时跳过检测 ────────────────────────────────────
print("\n[场景3] client=None → 跳过相似检测，正常新建")
_clear_test_queue()
p3, a3 = _make_kg_approval("深夜睡不着时刷手机")
store7 = CyberBrainStore()
kg_before3 = sum(len(store7._kg["nodes"]["Cyber_Minghan"][l])
                 for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))

with patch("builtins.input", side_effect=["y", "", ""]):
    handle_review(store7, client=None)

store8 = CyberBrainStore()
kg_after3 = sum(len(store8._kg["nodes"]["Cyber_Minghan"][l])
                for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))
check("client=None 时节点正常新建", kg_after3 == kg_before3 + 1)

# ── [4] 有相似节点选 i → 忽略，新建 ─────────────────────────────
print("\n[场景4] 相似节点 → 选 i 忽略，正常新建")
_clear_test_queue()
p4, a4 = _make_kg_approval("任务截止前刷视频逃避")
store9 = CyberBrainStore()
kg_before4 = sum(len(store9._kg["nodes"]["Cyber_Minghan"][l])
                 for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))

with patch("cyber_planner.find_similar_nodes", return_value=mock_similar), \
     patch("builtins.input", side_effect=["y", "i", "", ""]):
    handle_review(store9, client)

store10 = CyberBrainStore()
kg_after4 = sum(len(store10._kg["nodes"]["Cyber_Minghan"][l])
                for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics"))
check("选 i 忽略时新建节点（总数+1）", kg_after4 == kg_before4 + 1)

# ── 清理所有测试数据 ──────────────────────────────────────────────
print()
_clear_test_queue()
kg_clean = json.loads(KG_PATH.read_text())
for layer in ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics"):
    kg_clean["nodes"]["Cyber_Minghan"][layer] = [
        n for n in kg_clean["nodes"]["Cyber_Minghan"][layer]
        if n.get("source_mode") != "test"
    ]
KG_PATH.write_text(json.dumps(kg_clean, ensure_ascii=False, indent=2))
print("  \033[93m[INFO]\033[0m 测试数据已清理")

# ── 结论 ──────────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ /review 重复检测验收通过（C2）\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════════════\n")
