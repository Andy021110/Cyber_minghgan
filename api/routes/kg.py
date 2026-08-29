"""
api/routes/kg.py — /api/kg/* 路由
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/kg/nodes")
async def get_kg_nodes(
    layer:           Optional[str] = Query(None),
    includeArchived: bool          = Query(False),
):
    from api.main import _store
    from cyber_planner import get_kg_nodes as _get

    valid_layers = {"Id", "Ego", "Superego"}
    if layer and layer not in valid_layers:
        raise HTTPException(status_code=422, detail=f"layer 须为 {valid_layers}")

    nodes = _get(_store, layer=layer, include_archived=includeArchived)
    return {"nodes": nodes, "count": len(nodes)}


@router.get("/kg/nodes/{node_id}")
async def get_kg_node(node_id: str):
    from api.main import _store
    from cyber_planner import get_kg_node as _get

    node = _get(_store, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    return node


@router.get("/kg/graph")
async def get_kg_graph():
    from api.main import _store
    from cyber_planner import get_kg_graph as _get

    return _get(_store)
