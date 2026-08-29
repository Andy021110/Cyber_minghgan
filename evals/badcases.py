"""
evals/badcases.py — Badcase 登记处

为什么需要它：
实验驱动开发的关键不是"跑一次实验"，而是**失败样本可回放**。
一个只写在文档里的 badcase 会腐烂（无从验证它修没修好）；
一个可执行的 badcase 会变成回归测试——修好之后它就一直替你守着。

设计：
- 每条 badcase 自带 reproduce（种子数据 + 查询 + 期望包含的内容），**自包含**，
  不依赖真实 KG，任何人任何环境都能重放
- status: open（未修）/ fixed（已修且回放通过）
- regression_test：关联的回归测试，防止复发（没有测试兜底的修复视为未完成）

用法：
    python3 -m evals.replay              # 回放全部
    python3 -m evals.replay --only open  # 只看未修的
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_PATH = Path(__file__).resolve().parent / "badcases" / "cases.jsonl"

VALID_TYPES = ("retrieval", "answer", "infra", "quality")
VALID_STATUS = ("open", "fixed")


def cases_path(path: str | Path | None = None) -> Path:
    p = Path(path) if path else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_cases(path: str | Path | None = None) -> list[dict]:
    p = cases_path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def save_cases(cases: list[dict], path: str | Path | None = None) -> None:
    p = cases_path(path)
    body = "\n".join(json.dumps(c, ensure_ascii=False) for c in cases)
    p.write_text(body + "\n", encoding="utf-8")


def add_case(case: dict, path: str | Path | None = None) -> dict:
    """登记一条 badcase；自动补 id 与 found_at。"""
    cases = load_cases(path)
    if "id" not in case:
        n = len(cases) + 1
        case["id"] = f"BC-{n:03d}"
    case.setdefault("status", "open")
    case.setdefault("found_at", _today())
    _validate(case)
    cases.append(case)
    save_cases(cases, path)
    return case


def update_status(
    case_id: str, status: str, regression_test: str | None = None,
    fix_ref: str | None = None, path: str | Path | None = None,
) -> dict | None:
    cases = load_cases(path)
    for c in cases:
        if c.get("id") == case_id:
            c["status"] = status
            if regression_test:
                c["regression_test"] = regression_test
            if fix_ref:
                c["fix_ref"] = fix_ref
            save_cases(cases, path)
            return c
    return None


def list_open(path: str | Path | None = None) -> list[dict]:
    return [c for c in load_cases(path) if c.get("status") == "open"]


def _validate(case: dict) -> None:
    if case.get("type") not in VALID_TYPES:
        raise ValueError(f"type 必须是 {VALID_TYPES} 之一，收到 {case.get('type')!r}")
    if case.get("status") not in VALID_STATUS:
        raise ValueError(f"status 必须是 {VALID_STATUS} 之一，收到 {case.get('status')!r}")
    if case["type"] == "retrieval":
        r = case.get("reproduce") or {}
        for key in ("seed", "query"):
            if key not in r:
                raise ValueError(f"retrieval 类 badcase 的 reproduce 缺少 {key!r}")
        if not r.get("must_contain") and not r.get("must_not_contain"):
            raise ValueError(
                "retrieval 类 badcase 必须给出 must_contain 或 must_not_contain"
            )


def _today() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d")


__all__ = [
    "add_case",
    "cases_path",
    "load_cases",
    "list_open",
    "save_cases",
    "update_status",
    "Any",
]
