"""
test_similar_nodes.py — 相似节点检测验收（C1）

测试场景：
  [1]  明确相似的新观察 → 返回已有相似节点
  [2]  结果含 _similarity_reason 字段
  [3]  明确无关的新观察 → 返回空列表
  [4]  top_k 参数限制结果数量

运行：
  python3 pipelines/test_similar_nodes.py
"""

import sys, json
from pathlib import Path
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
print("  相似节点检测验收（C1）")
print("══════════════════════════════════════\n")

import anthropic
from cyber_planner import CyberBrainStore, find_similar_nodes

KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"
client  = anthropic.Anthropic()

# 写入两条语义相关的测试节点
store = CyberBrainStore()
n_similar = store.create(
    "Id", "工作任务卡住时→立刻起身买奶茶作为压力释放",
    "压力下的即时消费逃避行为", "测试证据",
    importance=6, source_mode="test",
)
n_unrelated = store.create(
    "Superego", "深夜刷手机后的自我批判和愧疚感",
    "道德自责模式", "测试证据",
    importance=4, source_mode="test",
)
store2 = CyberBrainStore()

# ── [1] 明确相似 → 找到相似节点 ──────────────────────────────────
print("[场景1+2] 相似内容检测")
new_similar = "项目卡住了，忍不住下楼买了一杯喜茶，买完才继续工作"
results = find_similar_nodes(new_similar, store2, client, top_k=3)
print(f"  输入：{new_similar}")
print(f"  结果：{[r['event_label'] for r in results]}")
found_similar = any(r["uuid"] == n_similar["uuid"] for r in results)
check("相似观察能找到已有相似节点", found_similar)
check("结果含 _similarity_reason 字段",
      all("_similarity_reason" in r for r in results))

# ── [3] 明确无关 → 空列表 ─────────────────────────────────────────
print("\n[场景3] 无关内容不返回结果")
new_unrelated = "今天学了线性代数的矩阵乘法，掌握了基本运算"
results2 = find_similar_nodes(new_unrelated, store2, client, top_k=3)
print(f"  输入：{new_unrelated}")
print(f"  结果：{[r['event_label'] for r in results2]}")
check("无关观察返回空列表", len(results2) == 0)

# ── [4] top_k 限制 ────────────────────────────────────────────────
print("\n[场景4] top_k 限制")
results3 = find_similar_nodes(new_similar, store2, client, top_k=1)
check("top_k=1 时结果不超过 1 条", len(results3) <= 1)

# ── 清理测试节点 ──────────────────────────────────────────────────
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
    print("  \033[92m✓ 相似节点检测验收通过（C1）\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════════════\n")
