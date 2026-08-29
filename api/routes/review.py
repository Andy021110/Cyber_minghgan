"""
api/routes/review.py — /api/review/* 路由
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _to_review_item(e: dict) -> dict:
    return {
        "id":             e.get("id", ""),
        "pendingId":      e.get("pending_id", ""),
        "timestamp":      e.get("timestamp", ""),
        "sourceMode":     e.get("source_mode", ""),
        "content":        e.get("content", ""),
        "rawEvidence":    e.get("raw_evidence", ""),
        "proposedRoute":  e.get("proposed_route", "log"),
        "proposedLayer":  e.get("proposed_layer"),
        "aiRationale":    e.get("ai_rationale", ""),
        "importance":     e.get("importance"),
        "importanceNote": e.get("importance_note"),
    }


class DecideRequest(BaseModel):
    decision:    str
    userNote:    str = ""
    importance:  Optional[int] = None
    description: Optional[str] = None
    visibility:  str = "private"


@router.get("/review/items")
async def get_review_items():
    from cyber_planner import get_review_items as _get
    items = _get()
    return {"items": [_to_review_item(i) for i in items], "count": len(items)}


@router.get("/review/count")
async def get_review_count():
    from cyber_planner import get_review_items as _get
    return {"count": len(_get())}


@router.post("/review/items/{item_id}/decide")
async def decide_review_item(item_id: str, req: DecideRequest):
    from api.main import _store
    from cyber_planner import process_review_decision

    valid = {"approved_kg", "approved_log", "rejected"}
    if req.decision not in valid:
        raise HTTPException(status_code=422, detail=f"decision 须为 {valid}")

    result = process_review_decision(
        _store,
        item_id,
        req.decision,
        user_note=req.userNote,
        importance=req.importance,
        description=req.description,
        visibility=req.visibility,
    )
    if not result["success"]:
        raise HTTPException(status_code=404, detail=f"条目 {item_id} 不存在")
    return {"success": True, "itemId": item_id}
