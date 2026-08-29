"""
pipelines/memory_maintenance.py — 记忆维护任务（后台，非 hot path）

设计依据（docs/LangGraph编排设计.md 第 5 节）：
遗忘与冲突检测属于 background 任务，不阻塞对话。默认 **dry-run 只提名**，
确认后才落盘，符合项目既有的 HITL 纪律。

用法：
    python3 pipelines/memory_maintenance.py forget             # 列出遗忘候选（不落盘）
    python3 pipelines/memory_maintenance.py forget --apply     # 执行归档
    python3 pipelines/memory_maintenance.py conflicts          # 列出标签冲突组
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from cyber_planner import CyberBrainStore, KG_PATH  # noqa: E402
from memory.lifecycle import (  # noqa: E402
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_MIN_AGE_DAYS,
    DEFAULT_MIN_EFFECTIVE,
    apply_forgetting,
)
from memory.versioning import conflict_candidates  # noqa: E402


def cmd_forget(store: CyberBrainStore, args: argparse.Namespace) -> int:
    now = datetime.now(timezone.utc)
    result = apply_forgetting(
        store,
        now=now,
        min_effective=args.min_effective,
        min_age_days=args.min_age,
        half_life_days=args.half_life,
        dry_run=not args.apply,
    )
    verb = "已归档" if args.apply else "遗忘候选"
    print(f"{verb}：{len(result)} 条")
    for item in result:
        print(
            f"  - [{item['event_label']}] {item['reason']}"
            f"（uuid {item['uuid'][:8]}…）"
        )
    return 0


def cmd_conflicts(store: CyberBrainStore, args: argparse.Namespace) -> int:
    conflicts = conflict_candidates(store)
    if not conflicts:
        print("未发现标签冲突。")
        return 0
    print(f"冲突组：{len(conflicts)} 组")
    for c in conflicts:
        print(f"  - {c['label']}（{c['count']} 条）")
        for n in c["nodes"]:
            print(f"      v{n['version']} {(n['created_at'] or '')[:10]}  {n['uuid'][:8]}…")
    if args.json:
        print(json.dumps(conflicts, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赛博明翰记忆维护（遗忘 / 冲突）")
    parser.add_argument("mode", choices=["forget", "conflicts"])
    parser.add_argument("--apply", action="store_true", help="真正执行归档（默认 dry-run）")
    parser.add_argument("--min-effective", type=float, default=DEFAULT_MIN_EFFECTIVE)
    parser.add_argument("--min-age", type=float, default=DEFAULT_MIN_AGE_DAYS)
    parser.add_argument("--half-life", type=float, default=DEFAULT_HALF_LIFE_DAYS)
    parser.add_argument("--json", action="store_true", help="conflicts 模式下输出 JSON")
    parser.add_argument("--kg", default=str(KG_PATH))
    args = parser.parse_args(argv)

    store = CyberBrainStore(kg_path=Path(args.kg))
    if args.mode == "forget":
        return cmd_forget(store, args)
    return cmd_conflicts(store, args)


if __name__ == "__main__":
    raise SystemExit(main())
