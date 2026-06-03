"""
test_prune_merge.py — /prune merge 存量合并验收（D1）

测试场景：
  [1]  scan_duplicate_pairs 检测到相似节点对
  [2]  选 1（保留A）→ winner importance+1，evidence 合并，loser 归档
  [3]  选 2（保留B）→ B 为 winner，A 为 loser
  [4]  选 s → 跳过，两条节点不变
  [5]  合并后 loser 的 archive_reason 含 "merged_into"

运行：
  python3 pipelines/test_prune_merge.py
"""

import sys, json, io
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import redirect_stdout
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

def capture(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()

print("\n══════════════════════════════════════")
print("  /prune merge 验收（D1）")
print("══════════════════════════════════════\n")

import anthropic
from cyber_planner import CyberBrainStore, scan_duplicate_pairs, _prune_merge

KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"
client  = anthropic.Anthropic()

# 准备两对测试节点：pair1 明确相似，pair2 明确不同
store = CyberBrainStore()
na = store.create("Id", "工作任务卡住时→立刻买奶茶逃避",
                  "压力逃避行为A", "证据A", importance=5, source_mode="test")
nb = store.create("Id", "项目遇到困难→起身下楼买饮料解压",
                  "压力逃避行为B", "证据B", importance=4, source_mode="test")
nc = store.create("Superego", "完成任务后过度自我批判",
                  "自责行为", "证据C", importance=6, source_mode="test")

# ── [1] scan_duplicate_pairs 检测相似对 ──────────────────────────
# 用只含 na/nb 的临时 KG 隔离，避免 AI 在 100+ 节点中漏判
print("[场景1] scan_duplicate_pairs 检测")
_full_kg = json.loads(KG_PATH.read_text())
_na_node = next(n for n in _full_kg["nodes"]["Cyber_Minghan"]["Id_Dynamics"] if n["uuid"] == na["uuid"])
_nb_node = next(n for n in _full_kg["nodes"]["Cyber_Minghan"]["Id_Dynamics"] if n["uuid"] == nb["uuid"])
_tmp_kg = {
    "schema_version": _full_kg["schema_version"],
    "created_at": _full_kg["created_at"],
    "nodes": {"Cyber_Minghan": {"Id_Dynamics": [_na_node, _nb_node], "Ego_Dynamics": [], "Superego_Dynamics": []}},
    "interactions": [], "metadata": {}, "updated_at": _full_kg["updated_at"],
}
_tmp_path = ROOT / "_test_isolated_kg.json"
_tmp_path.write_text(json.dumps(_tmp_kg, ensure_ascii=False, indent=2))
store_isolated = CyberBrainStore(_tmp_path)
pairs = scan_duplicate_pairs(store_isolated, client)
_tmp_path.unlink(missing_ok=True)
print(f"  检测到 {len(pairs)} 对")
for p in pairs:
    print(f"  · {p['node_a']['event_label'][:30]} ↔ {p['node_b']['event_label'][:30]}")
    print(f"    原因：{p['reason']}")
found_ab = any(
    {p["node_a"]["uuid"], p["node_b"]["uuid"]} == {na["uuid"], nb["uuid"]}
    for p in pairs
)
check("na/nb 被识别为重复对", found_ab)
check("返回结果含 reason 字段", len(pairs) == 0 or all("reason" in p for p in pairs))

# ── [2] 选 1 → 保留 A，归档 B ────────────────────────────────────
print("\n[场景2] 选 1 → 保留 A，归档 B")
mock_pairs_ab = [{"node_a": dict(na), "node_b": dict(nb), "reason": "同一压力→消费模式"}]
store3 = CyberBrainStore()
imp_a_before = na["importance"]  # 5
imp_b_before = nb["importance"]  # 4

with patch("cyber_planner.scan_duplicate_pairs", return_value=mock_pairs_ab), \
     patch("anthropic.Anthropic", return_value=client), \
     patch("builtins.input", side_effect=["1"]):
    _prune_merge(store3)

store4 = CyberBrainStore()
winner = next((n for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics")
               for n in store4._kg["nodes"]["Cyber_Minghan"][l]
               if n["uuid"] == na["uuid"]), None)
loser  = next((n for l in ("Id_Dynamics","Ego_Dynamics","Superego_Dynamics")
               for n in store4._kg["nodes"]["Cyber_Minghan"][l]
               if n["uuid"] == nb["uuid"]), None)

check("winner(A) importance 提升", winner and winner["importance"] == min(max(imp_a_before, imp_b_before)+1, 10))
check("winner(A) evidence 含 B 的证据", winner and "证据B" in (winner.get("evidence") or ""))
check("loser(B) 被归档", loser and loser.get("archived") is True)
check("loser(B) archive_reason 含 merged_into", loser and "merged_into" in (loser.get("archive_reason") or ""))

# ── [3] 选 2 → 保留 B，归档 A ────────────────────────────────────
print("\n[场景3] 选 2 → 保留 B，归档 A（重置数据后测试）")
# 先恢复测试节点状态
kg_reset = json.loads(KG_PATH.read_text())
for layer in ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics"):
    for n in kg_reset["nodes"]["Cyber_Minghan"][layer]:
        if n["uuid"] == na["uuid"]:
            n["importance"] = 5; n["evidence"] = "证据A"
            n["archived"] = False; n["archived_at"] = None; n["archive_reason"] = None
        if n["uuid"] == nb["uuid"]:
            n["importance"] = 4; n["evidence"] = "证据B"
            n["archived"] = False; n["archived_at"] = None; n["archive_reason"] = None
KG_PATH.write_text(json.dumps(kg_reset, ensure_ascii=False, indent=2))

store5 = CyberBrainStore()
fresh_na = next(n for l in ("Id_Dynamics",) for n in store5._kg["nodes"]["Cyber_Minghan"][l] if n["uuid"] == na["uuid"])
fresh_nb = next(n for l in ("Id_Dynamics",) for n in store5._kg["nodes"]["Cyber_Minghan"][l] if n["uuid"] == nb["uuid"])
mock_pairs_ab2 = [{"node_a": dict(fresh_na), "node_b": dict(fresh_nb), "reason": "重复"}]

with patch("cyber_planner.scan_duplicate_pairs", return_value=mock_pairs_ab2), \
     patch("anthropic.Anthropic", return_value=client), \
     patch("builtins.input", side_effect=["2"]):
    _prune_merge(store5)

store6 = CyberBrainStore()
node_a2 = next((n for l in ("Id_Dynamics",) for n in store6._kg["nodes"]["Cyber_Minghan"][l] if n["uuid"] == na["uuid"]), None)
node_b2 = next((n for l in ("Id_Dynamics",) for n in store6._kg["nodes"]["Cyber_Minghan"][l] if n["uuid"] == nb["uuid"]), None)
check("选2时 B 为 winner（未归档）", node_b2 and not node_b2.get("archived"))
check("选2时 A 为 loser（已归档）", node_a2 and node_a2.get("archived") is True)

# ── [4] 选 s → 跳过，两条不变 ────────────────────────────────────
print("\n[场景4] 选 s → 跳过")
store7 = CyberBrainStore()
fresh2_nb = next(n for l in ("Id_Dynamics",) for n in store7._kg["nodes"]["Cyber_Minghan"][l] if n["uuid"] == nb["uuid"])
mock_pairs_s = [{"node_a": dict(fresh2_nb), "node_b": dict(nc), "reason": "测试跳过"}]
with patch("cyber_planner.scan_duplicate_pairs", return_value=mock_pairs_s), \
     patch("anthropic.Anthropic", return_value=client), \
     patch("builtins.input", side_effect=["s"]):
    _prune_merge(store7)

store8 = CyberBrainStore()
nc_after = next((n for l in ("Superego_Dynamics",) for n in store8._kg["nodes"]["Cyber_Minghan"][l] if n["uuid"] == nc["uuid"]), None)
check("跳过后 nc 未被归档", nc_after and not nc_after.get("archived"))

# ── 清理所有测试节点 ──────────────────────────────────────────────
print()
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
    print("  \033[92m✓ /prune merge 验收通过（D1）\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════════════\n")
