"""
experiments/ledger.py — 实验台账

为什么需要它（这是本文件存在的全部理由）：
Agent 以 loop / harness 形式自主探索时，一晚上能做几十次决策：
λ 取 0.4 还是 0.6？interactions 要不要接进检索？阈值定多少？
这些**不是缺陷**（badcase 管不了），而是"这个选择到底合不合理"。

没有台账会发生什么：三天后你只知道当前值是 λ=0.4，
但不知道当初试过 0.6、结果是什么、为什么退回 0.4——
于是同一个实验会被反复重做，探索原地打转。

设计上的一条硬约束：**预登记**。
必须先写下假设和主指标（propose），再动手跑（conclude）。
顺序不能反。因为先跑后记的话，谁都会给已经做出的改动
编一个看起来合理的理由——那是确认偏误，不是实验。

用法：
    from experiments.ledger import propose, conclude, stats
    exp = propose(hypothesis="提高 λ 能提升 Recall@5",
                  change="hybrid λ 0.4→0.6", metric="Recall@5", baseline=0.62)
    # ... 跑实验 ...
    conclude(exp["id"], result=0.71, decision="adopt", note="语义召回补足明显")
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
_DEFAULT_PATH = _ROOT / "ledger.jsonl"

VALID_DECISIONS = ("adopt", "reject", "inconclusive")
VALID_STATUS = ("running", "done")


def ledger_path(path: str | Path | None = None) -> Path:
    p = Path(path) if path else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load(path: str | Path | None = None) -> list[dict]:
    p = ledger_path(path)
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


def _save(rows: list[dict], path: str | Path | None = None) -> None:
    p = ledger_path(path)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    p.write_text(body + "\n", encoding="utf-8")


def _next_id(rows: list[dict]) -> str:
    n = sum(1 for r in rows if str(r.get("id", "")).startswith("EXP-")) + 1
    return f"EXP-{n:03d}"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def propose(
    hypothesis: str,
    change: str,
    metric: str,
    baseline: Any = None,
    *,
    revert: str = "",
    related_badcase: str = "",
    path: str | Path | None = None,
) -> dict:
    """动手之前先登记假设。

    强制顺序的意义：先写假设再跑，结果才能证伪假设；
    反过来先跑再补假设，永远"符合预期"，实验就成了装饰。
    """
    if not hypothesis.strip():
        raise ValueError("hypothesis 不能为空——说不清在验证什么就别做")
    if not metric.strip():
        raise ValueError("metric 不能为空——没有主指标就无法判定成败")

    rows = load(path)
    exp = {
        "id": _next_id(rows),
        "date": _today(),
        "status": "running",
        "hypothesis": hypothesis,
        "change": change,
        "metric": metric,
        "baseline": baseline,
        "result": None,
        "delta": None,
        "decision": None,
        "note": "",
        "revert": revert,
        "related_badcase": related_badcase,
    }
    rows.append(exp)
    _save(rows, path)
    return exp


def conclude(
    exp_id: str,
    result: Any,
    decision: str,
    *,
    note: str = "",
    path: str | Path | None = None,
) -> dict:
    """登记结论。decision ∈ adopt / reject / inconclusive。"""
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision 必须是 {VALID_DECISIONS} 之一，收到 {decision!r}")

    rows = load(path)
    for r in rows:
        if r.get("id") == exp_id:
            r["status"] = "done"
            r["result"] = result
            r["decision"] = decision
            r["note"] = note
            r["delta"] = _delta(r.get("baseline"), result)
            _save(rows, path)
            return r
    raise KeyError(f"找不到实验 {exp_id!r}")


def _delta(baseline: Any, result: Any) -> Any:
    """数值才算差值；非数值（如"通过/不通过"）记为 None。"""
    if isinstance(baseline, (int, float)) and isinstance(result, (int, float)):
        return round(float(result) - float(baseline), 6)
    return None


def stats(path: str | Path | None = None) -> dict:
    """台账自身的健康度——用来回答「这套探索到底有没有在收敛」。"""
    rows = load(path)
    done = [r for r in rows if r.get("status") == "done"]
    return {
        "total": len(rows),
        "running": len(rows) - len(done),
        "done": len(done),
        "adopted": sum(1 for r in done if r.get("decision") == "adopt"),
        "rejected": sum(1 for r in done if r.get("decision") == "reject"),
        "inconclusive": sum(1 for r in done if r.get("decision") == "inconclusive"),
        "adoption_rate": (
            round(sum(1 for r in done if r.get("decision") == "adopt") / len(done), 3)
            if done else 0.0
        ),
        "with_baseline": sum(
            1 for r in rows if r.get("baseline") is not None
        ),
    }


def show(rows: list[dict] | None = None, path: str | Path | None = None) -> str:
    rows = rows if rows is not None else load(path)
    if not rows:
        return "（台账为空）"
    lines = [f"{'ID':<9}{'状态':<9}{'指标':<16}{'基线':<10}{'结果':<10}{'结论':<14}改动"]
    for r in rows:
        lines.append(
            f"{r['id']:<9}{r['status']:<9}{str(r['metric'])[:14]:<16}"
            f"{_fmt(r.get('baseline')):<10}{_fmt(r.get('result')):<10}"
            f"{str(r.get('decision') or '-'):<14}{r['change']}"
        )
    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)[:9]


__all__ = ["conclude", "ledger_path", "load", "propose", "show", "stats"]
