"""
test_exit_command.py — 验收 exit 指令识别逻辑

测试场景：
  [1] 所有触发词（exit / quit / 退出 / /exit 等）被正确识别
  [2] 普通对话不被误判为 exit
  [3] 大小写、首尾空格容错
  [4] confirm_exit 返回值正确（mock input）

运行：
  python3 pipelines/test_exit_command.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipelines"))

from assistant_utils import confirm_exit, is_exit_command

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
print("  exit 指令识别验收")
print("══════════════════════════════════════\n")

# ── [1] 触发词识别 ─────────────────────────────────────────────────
trigger_words = ["exit", "quit", "退出", "/exit", "/quit", "退出对话",
                 "EXIT", "QUIT", "Exit", " exit ", "退出 "]
for word in trigger_words:
    check(f"触发词识别: {repr(word)}", is_exit_command(word))

# ── [2] 普通对话不误判 ─────────────────────────────────────────────
print()
normal_inputs = [
    "今天吃了什么",
    "帮我分析一下",
    "exit这是什么",
    "我想退出这个习惯",
    "quit smoking",
    "",
    "  ",
]
for inp in normal_inputs:
    check(f"普通输入不误判: {repr(inp)}", not is_exit_command(inp))

# ── [3] confirm_exit Y/N ───────────────────────────────────────────
print()
with patch("builtins.input", return_value="Y"):
    check("confirm_exit: 输入 Y 返回 True", confirm_exit("健康教练") is True)

with patch("builtins.input", return_value="y"):
    check("confirm_exit: 输入 y 返回 True", confirm_exit("健康教练") is True)

with patch("builtins.input", return_value="N"):
    check("confirm_exit: 输入 N 返回 False", confirm_exit("健康教练") is False)

with patch("builtins.input", return_value=""):
    check("confirm_exit: 回车返回 False", confirm_exit() is False)

# ── 结论 ──────────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
if not errors:
    print("  \033[92m✓ exit 指令验收通过\033[0m")
else:
    print(f"  \033[91m✗ 有 {len(errors)} 项未通过：\033[0m")
    for e in errors:
        print(f"    · {e}")
print("══════════════════════════════════════\n")
