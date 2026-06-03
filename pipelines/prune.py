"""
prune.py — KG 节点老化评分模块（Phase 8a）

纯计算，无 I/O 副作用，不依赖 anthropic。
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

_LAYERS = ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics")


def _days_since(iso_str: Optional[str]) -> float:
    """计算距今天数；iso_str 为 None 时返回极大值（视为从未访问）。"""
    if not iso_str:
        return 9999.0
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(delta.total_seconds() / 86400, 0.0)
    except (ValueError, TypeError):
        return 9999.0


def compute_staleness(node: dict, config: dict) -> float:
    """
    老化分数 = days_since_reference / importance
    reference：优先取 last_accessed_at，若为 null 则取 created_at。
    importance 最小值限制为 1，防止除零。
    """
    ref = node.get("last_accessed_at") or node.get("created_at")
    days       = _days_since(ref)
    importance = max(node.get("importance", 5), 1)
    return round(days / importance, 2)


def _archive_reason_hint(node: dict, staleness: float, config: dict) -> str:
    threshold = config.get("staleness_threshold", 30)
    days      = _days_since(node.get("last_accessed_at") or node.get("created_at"))
    imp       = node.get("importance", 5)
    count     = node.get("access_count", 0)

    if count == 0:
        return f"从未被检索到，老化分 {staleness}"
    if days > 180:
        return f"{int(days)} 天未调用，重要度 {imp}，老化分 {staleness}"
    return f"{int(days)} 天未调用，调用仅 {count} 次，老化分 {staleness}"


def scan_candidates(kg_path: Path, config: dict) -> list:
    """
    扫描所有非归档节点，返回超过阈值的候选列表，按 staleness 降序。
    每条结果附加 _staleness 和 _archive_hint 字段（仅用于展示，不写回 KG）。
    """
    threshold = config.get("staleness_threshold", 30)
    kg        = json.loads(kg_path.read_text(encoding="utf-8"))
    node      = kg["nodes"]["Cyber_Minghan"]
    candidates = []

    for layer_key in _LAYERS:
        for item in node.get(layer_key, []):
            if item.get("archived"):
                continue
            s = compute_staleness(item, config)
            if s >= threshold:
                entry = dict(item)
                entry["_staleness"]     = s
                entry["_archive_hint"]  = _archive_reason_hint(item, s, config)
                candidates.append(entry)

    candidates.sort(key=lambda x: x["_staleness"], reverse=True)
    return candidates


def distribution_summary(kg_path: Path, config: dict) -> dict:
    """
    返回各区间节点数：
    {
      "above_threshold": N,   # staleness >= threshold（候选归档）
      "near_threshold":  N,   # threshold/2 <= staleness < threshold（接近阈值）
      "safe":            N,   # staleness < threshold/2
      "archived":        N,   # 已归档
      "total_active":    N,   # 非归档总数
    }
    """
    threshold = config.get("staleness_threshold", 30)
    near_min  = threshold / 2
    kg        = json.loads(kg_path.read_text(encoding="utf-8"))
    node      = kg["nodes"]["Cyber_Minghan"]

    above = near = safe = archived = 0
    for layer_key in _LAYERS:
        for item in node.get(layer_key, []):
            if item.get("archived"):
                archived += 1
                continue
            s = compute_staleness(item, config)
            if s >= threshold:
                above += 1
            elif s >= near_min:
                near += 1
            else:
                safe += 1

    return {
        "above_threshold": above,
        "near_threshold":  near,
        "safe":            safe,
        "archived":        archived,
        "total_active":    above + near + safe,
    }
