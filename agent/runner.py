"""
agent/runner.py — 组装生产运行时（真实 LLM + SQLite checkpointer）

短期记忆用 SQLite checkpointer 持久化（thread-scoped），
这样服务重启后同一 thread_id 仍能续上对话。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

from agent.graph import DEFAULT_SYSTEM, build_graph  # noqa: E402
from agent.models import AnthropicChatAdapter  # noqa: E402
from cyber_planner import (  # noqa: E402
    EPI_PATH,
    KG_PATH,
    MODEL,
    CyberBrainStore,
    build_system_prompt,
)
from memory.embeddings import get_provider as _get_provider  # noqa: E402
from memory.episodic_store import EpisodicStore  # noqa: E402

DEFAULT_CHECKPOINT_DB = _ROOT / "memory" / "checkpoints.db"


def build_sqlite_saver(db_path: str | Path = DEFAULT_CHECKPOINT_DB) -> SqliteSaver:
    """check_same_thread=False 是 FastAPI 多线程场景下的必需配置。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def build_llm(client: Any = None, model: str = MODEL, system: str = "") -> AnthropicChatAdapter:
    client = client or anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )
    return AnthropicChatAdapter(client=client, model=model, system=system)


def build_default_graph(
    kg_path: Path | str = KG_PATH,
    epi_path: Path | str = EPI_PATH,
    checkpoint_db: str | Path | None = DEFAULT_CHECKPOINT_DB,
    llm: Any = None,
    system_prompt: str = "",
    checkpointer: Any = None,
):
    """组装一张可用的图。

    测试请直接调 build_graph 并注入 FakeChatModel，不要走这里（这里会连真实 API）。
    """
    store = CyberBrainStore(kg_path=Path(kg_path), provider=_get_provider())
    episodic = EpisodicStore(Path(epi_path), provider=_get_provider())
    ckpt = checkpointer or (build_sqlite_saver(checkpoint_db) if checkpoint_db else None)
    prompt = system_prompt or build_system_prompt()
    llm = llm or build_llm(system=prompt)
    return build_graph(
        llm=llm,
        store=store,
        episodic=episodic,
        system_prompt=prompt,
        checkpointer=ckpt,
    )


__all__ = ["DEFAULT_CHECKPOINT_DB", "DEFAULT_SYSTEM", "build_default_graph", "build_llm",
           "build_sqlite_saver"]
