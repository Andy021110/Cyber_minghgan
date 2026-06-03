"""
assistant_utils.py — 各助手共用工具函数

目前包含：
  confirm_exit(mode_name)  — 统一 exit 指令 + Y/N 防误触确认
"""

_EXIT_WORDS = {"exit", "quit", "退出", "/exit", "/quit", "退出对话"}


def is_exit_command(user_input: str) -> bool:
    """判断用户输入是否为退出指令。"""
    return user_input.strip().lower() in _EXIT_WORDS


def confirm_exit(mode_name: str = "") -> bool:
    """
    显示退出确认提示，返回 True = 确认退出，False = 取消。
    mode_name: 助手名称，如 "健康教练"、"学习助手"
    """
    label = f"{mode_name}模式" if mode_name else "当前对话"
    try:
        ans = input(f"\n  确认退出{label}？(Y/N): ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        return True
    return ans == "Y"
