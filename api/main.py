"""
api/main.py — FastAPI 应用入口
启动：uvicorn api.main:app --reload --port 8000
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path，以便 import cyber_planner 和 pipelines.*
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "pipelines"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, kg, notifications, prune, review
from cyber_planner import (
    _CHAT,
    CyberBrainStore,
    build_public_system_prompt,
    build_system_prompt,
    get_provider,
)
from health_coach import (
    HEALTH_TOOLS,
)
from health_coach import (
    PROTOCOL_PATH as _HEALTH_PROTOCOL_PATH,
)
from health_coach import (
    build_kg_summary as _hc_build_kg_summary,
)
from health_coach import (
    build_system_prompt as _hc_build_system_prompt,
)

# ── 全局单例（所有路由复用，不在每次请求时重新初始化）─────────────

KG_PATH    = _ROOT / "yuanbao_cyber_minghan_kg.json"
LOGS_DIR   = _ROOT / "decision_logs"

_store = CyberBrainStore(kg_path=KG_PATH, provider=get_provider())

# 初始化模块级聊天状态（process_message 所需）
import os as _os

import anthropic as _anthropic

_CHAT["store"]         = _store
_CHAT["system_prompt"] = build_system_prompt()
_CHAT["system_prompt_private"] = _CHAT["system_prompt"]
_CHAT["system_prompt_public"]  = build_public_system_prompt()
_CHAT["client"]        = _anthropic.Anthropic(
    api_key=_os.environ.get("ANTHROPIC_API_KEY"),
    base_url=_os.environ.get("ANTHROPIC_BASE_URL"),
)
_CHAT["async_client"]  = _anthropic.AsyncAnthropic(
    api_key=_os.environ.get("ANTHROPIC_API_KEY"),
    base_url=_os.environ.get("ANTHROPIC_BASE_URL"),
)

# ── 健康管家专项状态 ────────────────────────────────────────────
if _HEALTH_PROTOCOL_PATH.exists():
    _hc_protocol_raw = _HEALTH_PROTOCOL_PATH.read_text(encoding="utf-8")
    # check_protocol_freshness uses input() interactively; in API mode skip that
    # and default to stale=False (protocol assumed fresh at server start).
    _hc_stale        = False
    _hc_protocol     = _hc_protocol_raw
    _hc_kg_summary   = _hc_build_kg_summary()
    _CHAT["health_system_prompt"] = _hc_build_system_prompt(_hc_kg_summary, _hc_protocol, _hc_stale)
else:
    _CHAT["health_system_prompt"] = _CHAT["system_prompt"]  # fallback
_CHAT["health_tools"] = HEALTH_TOOLS

# ── FastAPI 应用 ──────────────────────────────────────────────────

app = FastAPI(title="赛博明翰 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:3002", "http://127.0.0.1:3002"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    allow_credentials=False,
)

# ── 路由挂载 ─────────────────────────────────────────────────────

app.include_router(chat.router,          prefix="/api")
app.include_router(review.router,        prefix="/api")
app.include_router(kg.router,            prefix="/api")
app.include_router(prune.router,         prefix="/api")
app.include_router(notifications.router, prefix="/api")

# ── 健康检查 ─────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}
