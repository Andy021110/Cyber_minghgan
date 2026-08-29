"""
memory/lifecycle.py — 自动遗忘（Phase 2b）

设计：重要性不是一次性打的分，而是随时间衰减的「有效重要性」。

    effective = importance * 0.5 ** (days_since_last_access / half_life_days)

命中遗忘条件（有效重要性低于阈值 且 足够久未被访问）的节点进入归档候选，
由人工在 /prune 面板确认后归档 —— 自动遗忘只做「提名」，不做「删除」，
与项目既有的 HITL 写入纪律保持一致（删除是不可逆操作）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEFAULT_HALF_LIFE_DAYS = 180.0
DEFAULT_MIN_EFFECTIVE = 1.5
DEFAULT_MIN_AGE_DAYS = 90.0
MIN_EFFECTIVE_FLOOR = 0.5


def parse_ts(value: str | None) -> datetime | None:
    """解析 ISO 时间戳；失败返回 None（不抛异常，避免脏数据打断巡检）。"""
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def days_since(value: str | None, now: datetime | None = None) -> float:
    """距今天数；无时间戳时按 0 天处理（视为新数据，不触发遗忘）。"""
    dt = parse_ts(value)
    if dt is None:
        return 0.0
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def effective_importance(
    node: dict,
    now: datetime | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """有效重要性 = 基础 importance × 时间衰减。"""
    base = float(node.get("importance", 5) or 5)
    ref = node.get("last_accessed_at") or node.get("created_at")
    age = days_since(ref, now)
    decayed = base * (0.5 ** (age / half_life_days))
    return max(MIN_EFFECTIVE_FLOOR, round(decayed, 3))


def forget_candidates(
    nodes: list[dict],
    now: datetime | None = None,
    min_effective: float = DEFAULT_MIN_EFFECTIVE,
    min_age_days: float = DEFAULT_MIN_AGE_DAYS,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> list[dict]:
    """筛出应当被遗忘（归档）的候选节点。

    返回列表元素：{"uuid", "event_label", "effective", "age_days", "reason"}
    """
    out: list[dict] = []
    for node in nodes:
        if node.get("archived"):
            continue
        ref = node.get("last_accessed_at") or node.get("created_at")
        age = days_since(ref, now)
        if age < min_age_days:
            continue
        eff = effective_importance(node, now, half_life_days)
        if eff < min_effective:
            out.append(
                {
                    "uuid": node.get("uuid", ""),
                    "event_label": node.get("event_label", ""),
                    "effective": eff,
                    "age_days": round(age, 1),
                    "reason": f"有效重要性 {eff} < {min_effective}，且 {age:.0f} 天未被访问",
                }
            )
    out.sort(key=lambda x: x["effective"])
    return out


def apply_forgetting(
    store: Any,
    now: datetime | None = None,
    min_effective: float = DEFAULT_MIN_EFFECTIVE,
    min_age_days: float = DEFAULT_MIN_AGE_DAYS,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    dry_run: bool = False,
) -> list[dict]:
    """对候选节点执行归档（软删除，retrieve 不再返回）。

    dry_run=True 时只返回将要归档的清单，不落盘。
    幂等：已归档节点会被 forget_candidates 跳过，重复调用不会重复归档。
    """
    nodes = [n for lst in store._node_lists() for n in lst]
    candidates = forget_candidates(
        nodes, now, min_effective, min_age_days, half_life_days
    )
    if dry_run:
        return candidates

    now_iso = (now or datetime.now(timezone.utc)).isoformat()
    archived: list[dict] = []
    for c in candidates:
        try:
            store.update(
                c["uuid"],
                archived=True,
                archived_at=now_iso,
                archive_reason=f"auto-forget: {c['reason']}",
            )
            archived.append(c)
        except KeyError:
            continue
    return archived
