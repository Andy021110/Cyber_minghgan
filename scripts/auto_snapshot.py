#!/usr/bin/env python3
"""
scripts/auto_snapshot.py — 定期安全快照

为什么需要它：
探索以 Agent loop 形式连续进行，几小时的工作可能只存在于本地工作区。
机器故障 / 误操作 / 目录被清 = 全部丢失。定期推到 GitHub 是唯一
低成本的安全网。

安全约束（写进代码，不靠自觉）：
1. 有改动必须先跑测试，**不通过就不提交**——不把坏代码推上去
2. 只在 main 分支操作，且**绝不 force push**（历史强推后不可恢复）
3. **不自动打 tag**——tag 是里程碑，必须人来判断
4. rebase / merge 进行中时跳过，避免把中间状态提交进去
5. **无改动时不产生任何 commit**，避免把历史淹在琐碎快照里

用法：
    .venv/bin/python scripts/auto_snapshot.py            # 正常执行
    .venv/bin/python scripts/auto_snapshot.py --dry-run  # 只报告要做什么
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="安全快照：测试通过才提交并推送")
    ap.add_argument("--dry-run", action="store_true", help="只报告将做什么")
    args = ap.parse_args(argv)

    # 约束 4：rebase / merge 进行中不碰
    if (ROOT / ".git" / "rebase-merge").exists() or \
       (ROOT / ".git" / "rebase-apply").exists():
        print("跳过：rebase/merge 进行中")
        return 0

    # 约束 2：只在 main 操作
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != "main":
        print(f"跳过：当前分支 {branch!r} 不是 main")
        return 0

    dirty = git("status", "--porcelain").stdout.strip()
    ahead = git("log", "--oneline", "origin/main..HEAD").stdout.strip()

    # 约束 5：无改动不产生噪音 commit
    if not dirty and not ahead:
        print("无改动，跳过")
        return 0

    changes = [ln for ln in dirty.splitlines() if ln.strip()]

    # 约束 1：有改动先跑测试
    if changes:
        print(f"发现 {len(changes)} 项改动，先跑测试…")
        t = subprocess.run(
            [PY, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if t.returncode != 0:
            print("测试未通过，拒绝提交（坏代码不推上去）：")
            print((t.stdout or "")[-800:])
            return 1
        print("  测试通过")

    if args.dry_run:
        print(f"[dry-run] 将提交 {len(changes)} 项并推送 main")
        return 0

    git("add", "-A")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = git("commit", "-m", f"chore(snapshot): 自动快照 {ts}")
    if c.returncode != 0:
        print("提交失败:", (c.stdout or c.stderr)[-300:])
        return 1
    print(f"已提交：自动快照 {ts}")

    # 约束 2：绝不 force push
    p = git("push", "origin", "main")
    if p.returncode != 0:
        print("推送失败:", (p.stderr or "")[-300:])
        return 1
    print("已推送 origin/main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
