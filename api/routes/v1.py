"""
api/routes/v1.py — 版本化 API（Phase 3 API 工程化）

三个端点：
- POST /api/v1/chat          发消息；若触发写记忆，返回 interrupted + 审批请求
- POST /api/v1/chat/resume   人工审批后恢复（decision: approved_kg / approved_log / rejected）
- GET  /api/v1/memory/{tid}  查看某个 thread 的短期记忆快照（摘要、消息数）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agent.state import new_turn
from api.deps import get_graph

router = APIRouter()


class ChatRequest(BaseModel):
    thread_id: str = Field(..., description="会话线程 ID，相同 ID 续接同一段短期记忆")
    message: str = Field(..., description="用户消息")


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str = Field(
        "approved_kg",
        description="approved_kg（写入图谱）/ approved_log（只记日志）/ rejected（拒绝）",
    )


class ChatResponse(BaseModel):
    thread_id: str
    reply: str = ""
    interrupted: bool = False
    interrupts: list[dict] = []
    turn: int = 0


class MemorySnapshot(BaseModel):
    thread_id: str
    turn: int = 0
    working_summary: str = ""
    message_count: int = 0
    compacted_upto: int = 0


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _extract_reply(state: dict) -> str:
    for m in reversed(state.get("messages", [])):
        if getattr(m, "type", "") == "ai":
            content = getattr(m, "content", "")
            return content if isinstance(content, str) else str(content)
    return ""


def _extract_interrupts(state: dict) -> list[dict]:
    out = []
    for i in state.get("__interrupt__") or []:
        out.append({"id": getattr(i, "id", ""), "value": getattr(i, "value", None)})
    return out


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, graph: Any = Depends(get_graph)) -> ChatResponse:
    state = graph.invoke(new_turn(req.message), config=_cfg(req.thread_id))
    interrupts = _extract_interrupts(state)
    return ChatResponse(
        thread_id=req.thread_id,
        reply=_extract_reply(state),
        interrupted=bool(interrupts),
        interrupts=interrupts,
        turn=int(state.get("turn", 0)),
    )


@router.post("/chat/resume", response_model=ChatResponse)
def resume(req: ResumeRequest, graph: Any = Depends(get_graph)) -> ChatResponse:
    from langgraph.types import Command

    state = graph.invoke(Command(resume=req.decision), config=_cfg(req.thread_id))
    interrupts = _extract_interrupts(state)
    return ChatResponse(
        thread_id=req.thread_id,
        reply=_extract_reply(state),
        interrupted=bool(interrupts),
        interrupts=interrupts,
        turn=int(state.get("turn", 0)),
    )


@router.get("/memory/{thread_id}", response_model=MemorySnapshot)
def memory_snapshot(thread_id: str, graph: Any = Depends(get_graph)) -> MemorySnapshot:
    snapshot = graph.get_state(_cfg(thread_id))
    values = getattr(snapshot, "values", None)
    if not values:
        raise HTTPException(status_code=404, detail="thread 不存在")
    return MemorySnapshot(
        thread_id=thread_id,
        turn=int(values.get("turn", 0)),
        working_summary=str(values.get("working_summary", "")),
        message_count=len(values.get("messages", [])),
        compacted_upto=int(values.get("compacted_upto", 0)),
    )
