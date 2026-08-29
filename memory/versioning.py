"""
memory/versioning.py — 记忆冲突与版本化（Phase 2c）

认知会变：今天说「喜欢美式」，半年后说「改喝手冲了」。
若直接覆盖旧节点，就丢了「曾经喜欢美式」这条事实的演变过程；
若两条并存，检索时又会出现自相矛盾的记忆。

解法：supersede（取代）链 + 版本历史
- update_with_version：原地更新，但把旧快照压进 history（可回溯）
- supersede：新建节点取代旧节点，旧节点标记 superseded_by 并归档（检索不再返回，但事实不丢）
- conflict_candidates：找出「同一标签有多条活跃节点」的冲突，交 HITL 裁决

与 HITL 的边界：本模块只负责「发现冲突 + 执行取代」，是否取代由人工在审批面板决定。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_SNAPSHOT_FIELDS = ("event_label", "description", "evidence", "importance", "version")
_WS = re.compile(r"[\s，。、；：!！?？]+")

HISTORY_LIMIT = 5
DEFAULT_ACTOR = "system"


def normalize_label(label: str) -> str:
    """标签归一化：去空白与常见标点，用于冲突比对。"""
    return _WS.sub("", (label or "").strip()).lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot(node: dict) -> dict:
    snap = {k: node.get(k) for k in _SNAPSHOT_FIELDS}
    snap["version"] = int(node.get("version", 1) or 1)
    snap["archived_at"] = _now_iso()
    return snap


def update_with_version(
    store: Any,
    node_uuid: str,
    fields: dict,
    actor: str = DEFAULT_ACTOR,
    history_limit: int = HISTORY_LIMIT,
) -> dict:
    """带版本历史的更新：旧快照入 history，version +1。

    history 有上限（默认 5），超出丢弃最旧的 —— 避免节点无限膨胀。
    """
    lst, idx = store._find_by_uuid(node_uuid)
    node = lst[idx]

    history = list(node.get("history") or [])
    history.append(_snapshot(node))
    if len(history) > history_limit:
        history = history[-history_limit:]

    updates = dict(fields)
    updates["history"] = history
    updates["version"] = int(node.get("version", 1) or 1) + 1
    updates["updated_at"] = _now_iso()
    updates["updated_by"] = actor

    return store.update(node_uuid, **updates)


def supersede(
    store: Any,
    old_uuid: str,
    new_fields: dict,
    actor: str = DEFAULT_ACTOR,
    archive_reason: str = "superseded",
) -> dict:
    """用新节点取代旧节点：旧节点归档并指向新节点，新节点记录 supersedes。

    返回新创建的节点。
    """
    lst, idx = store._find_by_uuid(old_uuid)
    old = lst[idx]

    new_node = store.create(
        layer=old.get("layer", "Ego"),
        event_label=new_fields.get("event_label", old.get("event_label", "")),
        description=new_fields.get("description", old.get("description", "")),
        evidence=new_fields.get("evidence", old.get("evidence", "")),
        batch_id=new_fields.get("batch_id", "Supersede"),
        importance=int(new_fields.get("importance", old.get("importance", 5)) or 5),
        source_mode=new_fields.get("source_mode", "supersede"),
        visibility=old.get("visibility", "private"),
    )
    store.update(
        new_node["uuid"],
        supersedes=old_uuid,
        version=1,
        updated_at=_now_iso(),
        updated_by=actor,
    )

    store.update(
        old_uuid,
        superseded_by=new_node["uuid"],
        archived=True,
        archived_at=_now_iso(),
        archive_reason=archive_reason,
    )

    lst_new, idx_new = store._find_by_uuid(new_node["uuid"])
    return lst_new[idx_new]


def conflict_candidates(store: Any) -> list[dict]:
    """找出同一归一化标签下存在多条活跃节点的冲突组。

    返回：{"label", "nodes": [{uuid, event_label, created_at, version}]}
    供 HITL 面板选择保留哪条 / 是否 supersede。
    """
    buckets: dict[str, list[dict]] = {}
    for lst in store._node_lists():
        for node in lst:
            if node.get("archived"):
                continue
            key = normalize_label(node.get("event_label", ""))
            if not key:
                continue
            buckets.setdefault(key, []).append(node)

    out = []
    for label, nodes in buckets.items():
        if len(nodes) < 2:
            continue
        nodes_sorted = sorted(nodes, key=lambda n: n.get("created_at", ""))
        out.append(
            {
                "label": label,
                "count": len(nodes_sorted),
                "nodes": [
                    {
                        "uuid": n.get("uuid", ""),
                        "event_label": n.get("event_label", ""),
                        "created_at": n.get("created_at", ""),
                        "version": int(n.get("version", 1) or 1),
                    }
                    for n in nodes_sorted
                ],
            }
        )
    out.sort(key=lambda x: -x["count"])
    return out
