"""
test_kg_browse.py — /kg 节点浏览验收（B1 + B2）

测试场景：
  [1]  /kg 显示三层节点，输出含各层标题
  [2]  /kg 显示活跃节点总数和归档节点总数
  [3]  /kg id 只显示 Id 层节点
  [4]  /kg ego 只显示 Ego 层节点
  [5]  /kg superego 只显示 Superego 层节点
  [6]  /kg archived 只显示已归档节点
  [7]  归档节点在 /kg 全览中出现在底部归档区
  [8]  节点格式含 [importance] 和 event_label

运行：
  python3 pipelines/test_kg_browse.py
"""

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

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

def capture(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()

print("\n══════════════════════════════════════")
print("  /kg 浏览验收（B1 + B2）")
print("══════════════════════════════════════\n")

from cyber_planner import CyberBrainStore, _archive_node, handle_kg

KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"

# 准备测试节点
store = CyberBrainStore()
n_id  = store.create("Id",       "测试Id节点_browse",       "测试描述", "测试证据", importance=7, source_mode="test")
n_ego = store.create("Ego",      "测试Ego节点_browse",      "测试描述", "测试证据", importance=4, source_mode="test")
n_sup = store.create("Superego", "测试Superego节点_browse", "测试描述", "测试证据", importance=6, source_mode="test")
n_arc = store.create("Id",       "测试归档节点_browse",     "测试描述", "测试证据", importance=3, source_mode="test")

# 归档 n_arc
store2 = CyberBrainStore()
_archive_node(store2, n_arc["uuid"])
store3 = CyberBrainStore()

# ── [1] /kg 含三层标题 ────────────────────────────────────────────
out_all = capture(handle_kg, store3, "")
check("/kg 含 Id 层标题",       "Id — 本能欲望" in out_all)
check("/kg 含 Ego 层标题",      "Ego — 现实协商" in out_all)
check("/kg 含 Superego 层标题", "Superego — 道德规范" in out_all)

# ── [2] /kg 显示活跃/归档总数 ─────────────────────────────────────
check("/kg 标题含「活跃」和「归档」", "活跃" in out_all and "归档" in out_all)

# ── [3] /kg id 只显示 Id 层 ───────────────────────────────────────
out_id = capture(handle_kg, store3, "id")
check("/kg id 含 Id 层标题",        "Id — 本能欲望" in out_id)
check("/kg id 不含 Ego 层标题",     "Ego — 现实协商" not in out_id)
check("/kg id 不含 Superego 层标题","Superego — 道德规范" not in out_id)
check("/kg id 含测试 Id 节点",      "测试Id节点_browse" in out_id)

# ── [4] /kg ego 只显示 Ego 层 ────────────────────────────────────
out_ego = capture(handle_kg, store3, "ego")
check("/kg ego 含 Ego 层标题",    "Ego — 现实协商" in out_ego)
check("/kg ego 不含 Id 层标题",   "Id — 本能欲望" not in out_ego)
check("/kg ego 含测试 Ego 节点",  "测试Ego节点_browse" in out_ego)

# ── [5] /kg superego 只显示 Superego 层 ─────────────────────────
out_sup = capture(handle_kg, store3, "superego")
check("/kg superego 含 Superego 层标题", "Superego — 道德规范" in out_sup)
check("/kg superego 不含 Ego 层标题",    "Ego — 现实协商" not in out_sup)
check("/kg superego 含测试 Superego 节点","测试Superego节点_browse" in out_sup)

# ── [6] /kg archived 只显示归档节点 ──────────────────────────────
out_arc = capture(handle_kg, store3, "archived")
check("/kg archived 含归档节点标题",  "已归档" in out_arc)
check("/kg archived 含测试归档节点",  "测试归档节点_browse" in out_arc)
check("/kg archived 不含活跃 Id 节点","测试Id节点_browse" not in out_arc)

# ── [7] /kg 全览中归档节点在底部 ─────────────────────────────────
idx_superego = out_all.find("Superego — 道德规范")
# 搜索底部归档区的段落标题（含双空格+括号，与顶部标题行区分）
idx_archived_section = out_all.find("已归档  (")
check("归档区出现在 Superego 层之后", idx_archived_section > idx_superego)

# ── [8] 节点格式含 [importance] ──────────────────────────────────
check("Id 节点含 [7] importance 标记",  "[7]" in out_id)
check("Ego 节点含 [4] importance 标记", "[4]" in out_ego)

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
    print("  \033[92m✓ /kg 浏览验收通过（B1 + B2）\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════════════\n")
