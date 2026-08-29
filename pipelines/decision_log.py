"""
decision_log.py — 决策池读写工具（Phase 1 基础设施）

所有专项模式（health / study / work）共用此模块写入 decision_logs/。
cyber_planner.py 通过此模块读取通知和待审批条目。

Schema（pending 条目）：
  id              str   UUID，全局唯一
  timestamp       str   ISO 8601，含时区
  source_mode     str   "health" / "study" / "work"
  trigger_context str   切换前的用户意图摘要（可为空字符串）
  content         str   值得记录的观察描述
  raw_evidence    str   触发此条目的原始对话片段
  proposed_route  str?  批处理后填入："kg" 或 "log"，处理前为 null
  proposed_layer  str?  route=kg 时填入："Id"/"Ego"/"Superego"，否则为 null
  status          str   "pending" → "processing" → "approved"/"rejected"/"expired"

Schema（notification 条目）：
  id              str   UUID
  timestamp       str   ISO 8601
  type            str   "pending_ready"（批处理完成）/ "protocol_updated"（协议已更新）
  message         str   展示给用户的单行文本
  consumed        bool  false = 下次启动时展示，true = 已展示过
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT               = Path(__file__).parent.parent
LOGS_DIR           = ROOT / "decision_logs"
PENDING_PATH       = LOGS_DIR / "pending.jsonl"
APPROVAL_PATH      = LOGS_DIR / "awaiting_approval.jsonl"
NOTIFICATIONS_PATH = LOGS_DIR / "notifications.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _append(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_all(path: Path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _rewrite(path: Path, entries: list) -> None:
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + ("\n" if entries else ""),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════════
#  Pending 蓄水池
# ══════════════════════════════════════════════════════════════════

def write_pending(
    source_mode: str,
    content: str,
    raw_evidence: str,
    trigger_context: str = "",
    logs_dir: Path = LOGS_DIR,
) -> dict:
    """向蓄水池追加一条待处理条目，返回写入的完整 entry。"""
    entry = {
        "id":              uuid.uuid4().hex,
        "timestamp":       _now_iso(),
        "source_mode":     source_mode,
        "trigger_context": trigger_context,
        "content":         content,
        "raw_evidence":    raw_evidence,
        "proposed_route":  None,
        "proposed_layer":  None,
        "status":          "pending",
    }
    _append(logs_dir / "pending.jsonl", entry)
    return entry


def read_pending(status: Optional[str] = "pending", logs_dir: Path = LOGS_DIR) -> list:
    """读取蓄水池条目，按 status 过滤；status=None 返回全部。"""
    entries = _read_all(logs_dir / "pending.jsonl")
    if status is None:
        return entries
    return [e for e in entries if e.get("status") == status]


def count_pending(status: str = "pending", logs_dir: Path = LOGS_DIR) -> int:
    return len(read_pending(status, logs_dir=logs_dir))


def update_pending_status(
    entry_id: str,
    status: str,
    *,
    logs_dir: Path = LOGS_DIR,
    **extra_fields,
) -> bool:
    """按 id 更新 pending 条目的 status 及其他字段，返回是否找到并更新。"""
    pending_path = logs_dir / "pending.jsonl"
    entries = _read_all(pending_path)
    found = False
    for e in entries:
        if e.get("id") == entry_id:
            e["status"] = status
            e.update(extra_fields)
            found = True
            break
    if found:
        _rewrite(pending_path, entries)
    return found


# ══════════════════════════════════════════════════════════════════
#  Awaiting Approval 待审批池
# ══════════════════════════════════════════════════════════════════

def write_approval_item(
    pending_id: str,
    source_mode: str,
    content: str,
    raw_evidence: str,
    proposed_route: str,
    proposed_layer: Optional[str],
    ai_rationale: str,
    importance: Optional[int] = None,
    importance_note: Optional[str] = None,
    logs_dir: Path = LOGS_DIR,
) -> dict:
    """批处理完成后，写入一条待人工审批的分类结果。"""
    entry = {
        "id":               uuid.uuid4().hex,
        "pending_id":       pending_id,
        "timestamp":        _now_iso(),
        "source_mode":      source_mode,
        "content":          content,
        "raw_evidence":     raw_evidence,
        "proposed_route":   proposed_route,
        "proposed_layer":   proposed_layer,
        "ai_rationale":     ai_rationale,
        "importance":       importance,
        "importance_note":  importance_note,
        "status":           "awaiting",
    }
    _append(logs_dir / "awaiting_approval.jsonl", entry)
    return entry


def read_awaiting(logs_dir: Path = LOGS_DIR) -> list:
    return [e for e in _read_all(logs_dir / "awaiting_approval.jsonl") if e.get("status") == "awaiting"]


def resolve_approval(
    entry_id: str,
    decision: str,
    user_note: str = "",
    logs_dir: Path = LOGS_DIR,
) -> bool:
    """
    记录审批结果。
    decision: "approved_kg" / "approved_log" / "rejected"
    user_note: 用户输入的理解或拒绝理由
    """
    approval_path = logs_dir / "awaiting_approval.jsonl"
    entries = _read_all(approval_path)
    found = False
    for e in entries:
        if e.get("id") == entry_id:
            e["status"]        = decision
            e["user_note"]     = user_note
            e["resolved_at"]   = _now_iso()
            found = True
            break
    if found:
        _rewrite(approval_path, entries)
    return found


# ══════════════════════════════════════════════════════════════════
#  Notifications 通知队列
# ══════════════════════════════════════════════════════════════════

def write_notification(msg_type: str, message: str, logs_dir: Path = LOGS_DIR) -> dict:
    """
    msg_type: "pending_ready" | "protocol_updated"
    """
    entry = {
        "id":        uuid.uuid4().hex,
        "timestamp": _now_iso(),
        "type":      msg_type,
        "message":   message,
        "consumed":  False,
    }
    _append(logs_dir / "notifications.jsonl", entry)
    return entry


def read_unconsumed_notifications(logs_dir: Path = LOGS_DIR) -> list:
    return [e for e in _read_all(logs_dir / "notifications.jsonl") if not e.get("consumed", False)]


def consume_notification(entry_id: str, logs_dir: Path = LOGS_DIR) -> bool:
    """标记通知已展示。"""
    notifications_path = logs_dir / "notifications.jsonl"
    entries = _read_all(notifications_path)
    found = False
    for e in entries:
        if e.get("id") == entry_id:
            e["consumed"] = True
            found = True
            break
    if found:
        _rewrite(notifications_path, entries)
    return found
