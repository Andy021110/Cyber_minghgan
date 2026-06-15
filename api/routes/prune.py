"""
api/routes/prune.py — /api/prune/* 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ArchiveRequest(BaseModel):
    reason: str = ""


class BoostRequest(BaseModel):
    newImportance: int


@router.get("/prune/candidates")
async def get_prune_candidates():
    from cyber_planner import get_prune_candidates as _get
    from api.main import _store

    return _get(_store)


@router.post("/prune/{node_id}/archive")
async def archive_node(node_id: str, req: ArchiveRequest):
    from cyber_planner import archive_node as _archive
    from api.main import _store

    result = _archive(_store, node_id, req.reason)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    return {"success": True}


@router.post("/prune/{node_id}/boost")
async def boost_node(node_id: str, req: BoostRequest):
    from cyber_planner import boost_node_importance as _boost
    from api.main import _store

    if not 1 <= req.newImportance <= 10:
        raise HTTPException(status_code=422, detail="newImportance 须在 1–10 之间")

    result = _boost(_store, node_id, req.newImportance)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    return {"success": True, "newImportance": result["new_importance"]}
