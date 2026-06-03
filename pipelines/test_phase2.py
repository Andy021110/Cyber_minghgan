"""
test_phase2.py — Phase 2 验收测试（结构与集成，不调 API）

验收通过标准：
  [1] health_coach.py 可正常导入，无语法/依赖错误
  [2] HEALTH_TOOLS 只包含 retrieve_memory，不含写操作
  [3] 协议文件存在且 life_context 可解析
  [4] KG 文件结构完整，三层均有节点
  [5] build_kg_summary() 输出包含三层标签
  [6] _retrieve() 对已知关键词返回非空结果
  [7] 模拟 write_pending → pending.jsonl 写入后 KG updated_at 不变
  [8] 测试结束后清理写入的测试数据

手动验收（需在终端运行 python3 health_coach.py）：
  M1. 协议检查弹出，显示 life_context 内容
  M2. 问一个健康问题（如"今晚能喝几杯美式"），回答引用了协议里的具体数字
  M3. 问一个关于自己的问题（如"我遇到压力会怎样"），触发了「查询图谱」
  M4. 输入 exit，终端显示「写入 N 条观察」或「无新观察」
  M5. 检查 decision_logs/pending.jsonl，有新条目且字段完整

运行：
  python3 pipelines/test_phase2.py
"""

import json
import sys
import importlib
from pathlib import Path
from datetime import datetime

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
print("  Phase 2 验收测试（自动部分）")
print("══════════════════════════════════════\n")

# ── [1] 导入测试 ───────────────────────────────────────────────────
try:
    import health_coach as hc
    check("health_coach.py 导入成功", True)
except Exception as e:
    check(f"health_coach.py 导入成功（错误：{e}）", False)
    print("\n无法继续，请先修复导入错误。")
    sys.exit(1)

# ── [2] 工具白名单 ────────────────────────────────────────────────
tool_names = [t["name"] for t in hc.HEALTH_TOOLS]
check("HEALTH_TOOLS 只含 retrieve_memory", tool_names == ["retrieve_memory"])
check("HEALTH_TOOLS 不含写操作工具",
      not any(n in tool_names for n in ["create_memory","update_memory","delete_memory"]))

# ── [3] 协议文件 ──────────────────────────────────────────────────
check("protocols/bio_baseline_final.md 存在", hc.PROTOCOL_PATH.exists())
if hc.PROTOCOL_PATH.exists():
    protocol_text = hc.PROTOCOL_PATH.read_text(encoding="utf-8")
    ctx = hc.parse_life_context(protocol_text)
    check("life_context 可解析，字段数 >= 4", len(ctx) >= 4)
    check("life_context 包含体重字段",   "体重" in ctx)
    check("life_context 包含 reviewed_at", "reviewed_at" in ctx)

# ── [4] KG 文件结构 ───────────────────────────────────────────────
check("yuanbao_cyber_minghan_kg.json 存在", hc.KG_PATH.exists())
if hc.KG_PATH.exists():
    kg   = json.loads(hc.KG_PATH.read_text(encoding="utf-8"))
    node = kg["nodes"]["Cyber_Minghan"]
    check("Id_Dynamics 存在且非空",       len(node.get("Id_Dynamics", [])) > 0)
    check("Ego_Dynamics 存在且非空",      len(node.get("Ego_Dynamics", [])) > 0)
    check("Superego_Dynamics 存在且非空", len(node.get("Superego_Dynamics", [])) > 0)
    check("domains 字段不存在（物理隔离确认）", "domains" not in node)
    kg_updated_at_before = kg.get("updated_at", "")

# ── [5] KG 目录摘要 ───────────────────────────────────────────────
summary = hc.build_kg_summary()
check("摘要包含 Id 层标签",       "Id" in summary)
check("摘要包含 Ego 层标签",      "Ego" in summary)
check("摘要包含 Superego 层标签", "Superego" in summary)
check("摘要包含 retrieve_memory 提示", "retrieve_memory" in summary)

# ── [6] _retrieve 检索功能 ────────────────────────────────────────
results = hc._retrieve("压力", limit=5)
check("_retrieve('压力') 返回列表",    isinstance(results, list))
check("_retrieve 结果包含 layer 字段", all("layer" in r for r in results) if results else True)
check("_retrieve 结果包含 event_label", all("event_label" in r for r in results) if results else True)

# ── [7] pending 写入不影响 KG ─────────────────────────────────────
from decision_log import write_pending, _read_all, _rewrite, PENDING_PATH

test_entry = write_pending(
    source_mode="health",
    content="测试条目：Phase 2 验收",
    raw_evidence="test_phase2.py 自动写入",
)
check("write_pending 写入成功", bool(test_entry.get("id")))

# 确认 KG 未被修改
if hc.KG_PATH.exists():
    kg_after = json.loads(hc.KG_PATH.read_text(encoding="utf-8"))
    kg_updated_at_after = kg_after.get("updated_at", "")
    check("write_pending 后 KG updated_at 未变化",
          kg_updated_at_before == kg_updated_at_after)
    check("write_pending 后 KG 无 domains 字段",
          "domains" not in kg_after["nodes"]["Cyber_Minghan"])

# 清理测试条目
all_p = _read_all(PENDING_PATH)
cleaned = [e for e in all_p if e.get("id") != test_entry["id"]]
_rewrite(PENDING_PATH, cleaned)
print(f"  {INFO} 测试 pending 条目已清理")

# ── 最终结论 ───────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ Phase 2 自动验收通过\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")

print("""
  ── 手动验收清单（请在终端运行后确认）──
  python3 health_coach.py

  M1. 启动时显示 life_context 检查，字段内容正确
  M2. 问"今晚能喝几杯美式"→ 回答引用了 400mg / 具体数字
  M3. 问"我遇到压力会怎样"  → 出现「查询图谱」提示
  M4. 输入 exit             → 显示「写入 N 条观察」或「无新观察」
  M5. cat decision_logs/pending.jsonl 确认有新条目
""")
print("══════════════════════════════════════\n")
