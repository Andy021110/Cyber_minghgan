"""
api/schemas.py — Pydantic 数据模型（对应 TECH_SPEC 第五章 5.7）
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class KGNode(BaseModel):
    id:            str
    label:         str
    layer:         Literal["Id", "Ego", "Superego"]
    description:   str
    importance:    int
    evidence:      list[str]
    createdAt:     Optional[str] = None
    lastAccessed:  Optional[str] = None
    archived:      bool = False
    archiveReason: Optional[str] = None


class ReviewItem(BaseModel):
    id:             str
    pendingId:      str
    timestamp:      str
    sourceMode:     str
    content:        str
    rawEvidence:    str
    proposedRoute:  str
    proposedLayer:  Optional[str] = None
    aiRationale:    str
    importance:     Optional[int] = None
    importanceNote: Optional[str] = None


class Notification(BaseModel):
    id:        str
    timestamp: str
    type:      Literal["pending_ready", "protocol_updated"]
    message:   str


class PruneCandidate(BaseModel):
    node:          KGNode
    stalenessScore: float
    severity:      Literal["critical", "warning", "healthy"]
