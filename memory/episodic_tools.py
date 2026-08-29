"""
L0 Episodic tool schemas + dispatch（评测 / 产品共用）

不写 L1 KG；只操作 EpisodicStore。
"""

from __future__ import annotations

import json
from typing import Any

from memory.episodic_store import EpisodicStore

EPISODIC_TOOLS: list[dict] = [
    {
        "name": "retrieve_episode",
        "description": (
            "Search L0 episodic dialogue memory by keyword. "
            "Use for locating specific facts, names, preferences, amounts, event mentions. "
            "Default limit 10. For exhaustive counting across all sessions, prefer list_episodes first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Keyword or short phrase to search in episode text.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10, max 30).",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 30,
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "list_episodes",
        "description": (
            "List episodes in chronological order with pagination. "
            "Use when counting, aggregating, ordering events, or when keyword search may miss items. "
            "Scan with offset until returned count < limit. Summaries are truncated; "
            "call retrieve_episode for details if needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "offset": {
                    "type": "integer",
                    "description": "Start index (0-based).",
                    "default": 0,
                    "minimum": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Page size (default 20, max 50).",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50,
                },
                "order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort by timestamp string.",
                    "default": "asc",
                },
            },
            "required": [],
        },
    },
]


def dispatch_episodic_tool(epi: EpisodicStore, name: str, args: dict[str, Any]) -> Any:
    if name == "retrieve_episode":
        kw = str(args.get("keyword", ""))
        limit = int(args.get("limit") or 10)
        limit = max(1, min(limit, 30))
        return epi.search(kw, limit=limit)
    if name == "list_episodes":
        offset = int(args.get("offset") or 0)
        limit = int(args.get("limit") or 20)
        order = str(args.get("order") or "asc")
        return epi.list_episodes(offset=offset, limit=limit, order=order)
    raise ValueError(f"unknown episodic tool: {name!r}")


def tool_result_content(result: Any) -> str:
    return json.dumps(result, ensure_ascii=False)
