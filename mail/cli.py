"""
mail/cli.py — 邮件适配器命令行验证

用法：
    .venv/bin/python -m mail.cli check              # 两个邮箱各拉最近 5 封（只读）
    .venv/bin/python -m mail.cli check -n 3         # 各拉 3 封
    .venv/bin/python -m mail.cli check gmail        # 只查某一个
    .venv/bin/python -m mail.cli send               # 163 → Gmail 互发一封测试信

设计原则：
- `check` 全程只读，不标已读、不改邮箱任何状态
- `send` 只在你自己的两个邮箱之间互发，不碰任何第三方
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv                       # noqa: E402

from mail.adapter import PROVIDERS, MailConfigError, fetch_recent, send  # noqa: E402

ALL = ("gmail", "netease")


def _show(provider: str, limit: int) -> bool:
    try:
        mails = fetch_recent(provider, limit=limit)
    except MailConfigError as exc:
        print(f"  [{provider}] 配置未就绪：{exc}")
        return False
    except Exception as exc:                          # 网络/认证失败
        # 只报类型与简要原因，绝不回显凭证
        print(f"  [{provider}] 失败：{type(exc).__name__}: {str(exc)[:120]}")
        return False

    if not mails:
        print(f"  [{provider}] 收件箱为空")
        return True
    print(f"  [{provider}] 最近 {len(mails)} 封：")
    for i, m in enumerate(mails, 1):
        print(f"    {i}. {m['subject'][:44]}")
        print(f"       发件: {m['from'][:56]}")
        print(f"       时间: {m['date'][:31]}")
        if m["body"]:
            print(f"       摘要: {m['body'][:70]}")
    return True


def main(argv: list[str] | None = None) -> int:
    load_dotenv(_ROOT / ".env", override=True)

    ap = argparse.ArgumentParser(description="邮件适配器验证")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="拉取最近邮件（只读）")
    p_check.add_argument("provider", nargs="?", choices=ALL, help="默认两个都查")
    p_check.add_argument("-n", type=int, default=5)

    p_send = sub.add_parser("send", help="两个邮箱互发一封测试信")
    p_send.add_argument("--reverse", action="store_true",
                        help="反向发送（Gmail → 163）")

    args = ap.parse_args(argv)

    if args.cmd == "check":
        targets = (args.provider,) if args.provider else ALL
        print("=== 邮件读取验证（只读，不标已读）===")
        ok = [_show(p, args.n) for p in targets]
        return 0 if all(ok) else 1

    # send：只在你自己的两个邮箱之间互发
    src, dst = ("netease", "gmail") if not args.reverse else ("gmail", "netease")
    from_env = {"gmail": "GMAIL_ADDRESS", "netease": "NETEASE_ADDRESS"}
    to_addr = os.environ.get(from_env[dst], "").strip()
    if not to_addr:
        print(f"无法发送：{from_env[dst]} 未设置")
        return 1
    try:
        send(src, to_addr, "赛博明翰 · 收发验证",
             "这是一封自动化验证邮件，用于确认收发链路通畅。可忽略。")
    except Exception as exc:
        print(f"发送失败：{type(exc).__name__}: {str(exc)[:120]}")
        return 1
    print(f"已从 {src} 发送到 {dst}（{to_addr}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
