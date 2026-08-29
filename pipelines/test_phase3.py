"""
test_phase3.py — Phase 3 验收测试（结构部分，不调 API）

自动验收：
  [1] cyber_planner 可正常导入
  [2] handle_switch 函数存在
  [3] _MODE_MAP 包含 health
  [4] /switch 优先于普通 / 指令（代码顺序验证）
  [5] _extract_trigger_context 正确提取最后一条用户消息
  [6] _extract_trigger_context 在无消息时返回空字符串
  [7] handle_switch 对未知模式返回 False 且不崩溃

手动验收（在终端运行）：
  python3 cyber_planner.py

  M1. 聊几句，然后输入 /switch health
      → 弹出确认框，显示切换说明 + 带入摘要
  M2. 确认框输入 N
      → 取消，继续当前对话，不进入健康模式
  M3. 再次 /switch health，输入 Y
      → 进入健康教练模式（life_context 检查出现）
  M4. 健康教练 exit 后，cyber_planner session 自动结束
  M5. KG updated_at 未变化

运行：
  python3 pipelines/test_phase3.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
errors = []

def check(label: str, condition: bool):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        errors.append(label)

print("\n══════════════════════════════════════")
print("  Phase 3 验收测试（自动部分）")
print("══════════════════════════════════════\n")

# ── [1] 导入 ──────────────────────────────────────────────────────
try:
    import cyber_planner as cp
    check("cyber_planner.py 导入成功", True)
except Exception as e:
    check(f"cyber_planner.py 导入成功（错误：{e}）", False)
    sys.exit(1)

# ── [2] handle_switch 存在 ────────────────────────────────────────
check("handle_switch 函数存在",          hasattr(cp, "handle_switch"))
check("_extract_trigger_context 存在",   hasattr(cp, "_extract_trigger_context"))
check("_MODE_MAP 存在",                  hasattr(cp, "_MODE_MAP"))

# ── [3] _MODE_MAP 包含 health ─────────────────────────────────────
check("_MODE_MAP 包含 health",           "health" in cp._MODE_MAP)
check("health 映射到 health_coach",      cp._MODE_MAP.get("health") == "health_coach")

# ── [4] /switch 在代码里出现在 /handle_admin 之前 ─────────────────
src = Path(ROOT / "cyber_planner.py").read_text()
switch_pos = src.find("/switch ")
admin_pos  = src.find("handle_admin_command")
check("/switch 拦截在 handle_admin_command 之前", 0 < switch_pos < admin_pos)

# ── [5] _extract_trigger_context 正确提取 ────────────────────────
messages = [
    {"role": "user",      "content": "你好"},
    {"role": "assistant", "content": [type("T", (), {"type": "text", "text": "嗯"})()]},
    {"role": "user",      "content": "我最近写代码卡住就想买奶茶"},
]
ctx = cp._extract_trigger_context(messages)
check("提取到最后一条用户消息", "奶茶" in ctx)
check("长度不超过 103 字（含省略号）", len(ctx) <= 103)

# ── [6] 无消息时返回空字符串 ──────────────────────────────────────
check("无消息时返回空字符串", cp._extract_trigger_context([]) == "")
check("只有 assistant 消息时返回空字符串",
      cp._extract_trigger_context([
          {"role": "assistant", "content": []}
      ]) == "")

# ── [7] 未知模式返回 False 不崩溃 ────────────────────────────────
result = cp.handle_switch("unknown_mode", [])
check("未知模式返回 False", result is False)

# ── 最终结论 ───────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ Phase 3 自动验收通过\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")

print("""
  ── 手动验收清单 ──
  python3 cyber_planner.py

  M1. 聊几句 → 输入 /switch health
      确认框出现，显示带入摘要
  M2. 输入 N → 取消，继续聊天
  M3. 输入 /switch health → 输入 Y
      → 健康教练模式启动
  M4. 健康教练 exit → cyber_planner session 结束
  M5. KG updated_at 未变化
""")
print("══════════════════════════════════════\n")
