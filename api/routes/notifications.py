"""
api/routes/notifications.py — /api/notifications/* 路由
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

_LOGS_DIR = Path(__file__).parent.parent.parent / "decision_logs"


def _to_notification(e: dict) -> dict:
    return {
        "id":        e.get("id", ""),
        "timestamp": e.get("timestamp", ""),
        "type":      e.get("type", ""),
        "message":   e.get("message", ""),
    }


@router.get("/notifications")
async def get_notifications():
    from decision_log import read_unconsumed_notifications
    items = read_unconsumed_notifications(logs_dir=_LOGS_DIR)
    return {
        "notifications": [_to_notification(n) for n in items],
        "count": len(items),
    }


@router.post("/notifications/{notification_id}/consume")
async def consume_notification(notification_id: str):
    from decision_log import consume_notification as _consume
    found = _consume(notification_id, logs_dir=_LOGS_DIR)
    if not found:
        raise HTTPException(status_code=404, detail=f"通知 {notification_id} 不存在")
    return {"success": True}
