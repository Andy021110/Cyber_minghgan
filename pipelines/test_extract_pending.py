"""
test_extract_pending.py — 验收 _EXTRACT_SYSTEM 提取逻辑

测试场景：
  [1] 饮食记录（单次，无触发→反应结构）应被提取
  [2] 触发→反应模式应被提取
  [3] 纯通用知识问答不应被提取

运行：
  python3 pipelines/test_extract_pending.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import anthropic

from health_coach import extract_pending

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
print("  _EXTRACT_SYSTEM 提取逻辑验收")
print("══════════════════════════════════════\n")

client = anthropic.Anthropic()

# ── [1] 饮食记录：单次但应被提取 ──────────────────────────────────
messages_food = [
    {"role": "user",      "content": "今天午饭吃了和府捞面的草本猪软骨面，吃了好多，很撑"},
    {"role": "assistant", "content": [type("T", (), {"type": "text", "text": "好，先把这顿算清楚。估算约750-850kcal，已触线协议上限。"})()]},
]
result1 = extract_pending(messages_food, client)
print("[场景1] 饮食记录（单次）")
print(f"  提取结果：{result1}")
check("饮食记录被提取（len >= 1）", len(result1) >= 1)
check("content 字段存在",           all("content" in r for r in result1))
check("raw_evidence 字段存在",      all("raw_evidence" in r for r in result1))

# ── [2] 触发→反应模式：必须提取 ──────────────────────────────────
messages_pattern = [
    {"role": "user",      "content": "下午为了工作压力大，我额外多喝了两杯美式，比平常多"},
    {"role": "assistant", "content": [type("T", (), {"type": "text", "text": "今天咖啡因总量已到头，协议第25条上限400mg。"})()]},
]
result2 = extract_pending(messages_pattern, client)
print("\n[场景2] 触发→反应模式")
print(f"  提取结果：{result2}")
check("触发→反应模式被提取（len >= 1）", len(result2) >= 1)

# ── [3] 纯通用问答：不应提取 ─────────────────────────────────────
messages_generic = [
    {"role": "user",      "content": "碳水化合物和脂肪哪个更容易让人发胖？"},
    {"role": "assistant", "content": [type("T", (), {"type": "text", "text": "两者都可能导致热量盈余，关键在总热量。"})()]},
]
result3 = extract_pending(messages_generic, client)
print("\n[场景3] 纯通用知识问答")
print(f"  提取结果：{result3}")
check("纯问答不提取（len == 0）", len(result3) == 0)

# ── [4] 混合对话：两条都应被提取 ─────────────────────────────────
messages_mixed = [
    {"role": "user",      "content": "今天午饭吃了猪脚饭，米饭吃了很多，有点撑"},
    {"role": "assistant", "content": [type("T", (), {"type": "text", "text": "这顿约700kcal，碳水偏高。"})()]},
    {"role": "user",      "content": "下午工作很烦，又去买了一杯奶茶解压"},
    {"role": "assistant", "content": [type("T", (), {"type": "text", "text": "这是典型的情绪性进食，注意奶茶的糖分。"})()]},
]
result4 = extract_pending(messages_mixed, client)
print("\n[场景4] 混合对话（饮食 + 情绪性进食）")
print(f"  提取结果：{result4}")
check("混合对话提取 >= 2 条", len(result4) >= 2)

# ── 结论 ──────────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ _EXTRACT_SYSTEM 验收通过\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════════════\n")
