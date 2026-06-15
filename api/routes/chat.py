"""
api/routes/chat.py — /api/chat 路由（SSE 流式对话）
"""

import hmac
import json
import os
import asyncio
import anthropic
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from cyber_planner import process_message
from cyber_planner import _CHAT as _state

router = APIRouter()


class ChatRequest(BaseModel):
    npcId:      str
    message:    str
    privateKey: str = ""


async def _auto_reflect() -> None:
    """API 模式反刍：分析近期对话 → 有新特征时自动写入 KG → 截断消息历史。"""
    from cyber_planner import _CHAT, _reflect, _safe_truncate, REFLECT_EVERY

    state  = _CHAT
    client = state.get("client")
    store  = state.get("store")
    msgs   = state["messages"]

    if not client or not store:
        state["messages"] = _safe_truncate(msgs, keep_turns=2)
        return

    user_idx = [
        i for i, m in enumerate(msgs)
        if m["role"] == "user" and isinstance(m["content"], str)
    ]
    cut    = user_idx[-REFLECT_EVERY] if len(user_idx) >= REFLECT_EVERY else 0
    recent = msgs[cut:]

    feature = await asyncio.to_thread(_reflect, client, recent)
    if feature.upper() != "NONE":
        store.create(
            layer="Ego",
            event_label=feature[:40],
            description=feature,
            evidence="[API 反刍引擎自动提取]",
            batch_id="Reflection",
            importance=5,
            source_mode="reflection",
        )
    state["messages"] = _safe_truncate(msgs, keep_turns=2)


@router.post("/chat")
async def chat(req: ChatRequest):
    """向 NPC 发送消息，以 SSE 流式返回 AI 回复。"""
    _PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
    is_private = bool(_PRIVATE_KEY) and hmac.compare_digest(req.privateKey, _PRIVATE_KEY)

    if req.npcId == "health_coach":
        resolved_prompt = _state.get("health_system_prompt", _state["system_prompt"])
        resolved_tools  = _state.get("health_tools", None)
    else:
        resolved_prompt = (
            _state.get("system_prompt_private", _state["system_prompt"])
            if is_private
            else _state.get("system_prompt_public", _state["system_prompt"])
        )
        resolved_tools = None  # use default CYBER_TOOLS

    async def event_stream():
        full_text:           list[str] = []
        reflection_triggered: bool     = False

        try:
            async for token in process_message(
                    req.message,
                    system_prompt_override=resolved_prompt,
                    tools_override=resolved_tools,
                ):
                if token == "[REFLECTION_TRIGGERED]":
                    reflection_triggered = True
                    if is_private:
                        await _auto_reflect()
                elif token.startswith("[TOOL_LABEL:"):
                    label = token[12:-1]
                    yield f"data: {json.dumps({'type': 'tool', 'label': label})}\n\n"
                else:
                    full_text.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except anthropic.APIError:
            pass

        yield f"data: {json.dumps({'type': 'done', 'fullText': ''.join(full_text)})}\n\n"
        yield f"data: {json.dumps({'type': 'reflection', 'triggered': reflection_triggered})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/chat/history")
async def clear_history():
    """清空对话历史，开启新一轮对话。"""
    from cyber_planner import _CHAT
    _CHAT["messages"] = []
    _CHAT["turns"]    = 0
    return {"cleared": True}
