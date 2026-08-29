# Track B: Health Coach Backend Plan

**Goal:** Route `npcId='health_coach'` to its own system prompt (KG read-only + health protocol) instead of sharing 赛博明翰's system prompt. Use `health_coach.py`'s existing `build_system_prompt()`, `build_kg_summary()`, and `HEALTH_TOOLS`.

**Tech Stack:** Python 3.9, FastAPI, existing `health_coach.py`, `cyber_planner.py`

**Key facts:**
- `health_coach.py`: has `HEALTH_TOOLS` (read-only retrieve_memory), `build_system_prompt(kg_summary, protocol_text, stale)`, `build_kg_summary()`
- `PROTOCOL_PATH = ROOT / "protocols" / "bio_baseline_final.md"` — file exists
- `process_message()` in `cyber_planner.py` currently hardcodes `CYBER_TOOLS` — needs a `tools` param
- `api/main.py` initializes `_CHAT` state once at startup — add health state there
- `api/routes/chat.py` already selects `resolved_prompt` by `is_private` — extend to also select by `npcId`

---

### Task B1: Add `tools` parameter to `process_message`

**Files:**
- Modify: `cyber_planner.py` — function `process_message` around line 1648

Find the `process_message` signature and the two places it uses `CYBER_TOOLS`. Add an optional `tools` parameter.

Current signature (around line 1648):
```python
async def process_message(
    user_message: str | None = None,
    *,
    system_prompt_override: str | None = None,
) -> AsyncGenerator[str, None]:
```

New signature:
```python
async def process_message(
    user_message: str | None = None,
    *,
    system_prompt_override: str | None = None,
    tools_override: list | None = None,
) -> AsyncGenerator[str, None]:
```

Inside the function body, find every occurrence of `tools=CYBER_TOOLS` and replace with:
```python
tools=tools_override if tools_override is not None else CYBER_TOOLS,
```

There are exactly 2 occurrences of `tools=CYBER_TOOLS` in `process_message`. Replace both.

- [ ] Read `cyber_planner.py` lines 1648–1730 to see exact context
- [ ] Add `tools_override: list | None = None` to the signature
- [ ] Replace both `tools=CYBER_TOOLS` with `tools=tools_override if tools_override is not None else CYBER_TOOLS`
- [ ] Run: `python3 -c "from cyber_planner import process_message; print('OK')"` — expect `OK`
- [ ] Commit: `git add cyber_planner.py && git commit -m "feat: add tools_override param to process_message"`

---

### Task B2: Initialize health coach state in api/main.py

**Files:**
- Modify: `api/main.py`

After the existing `_CHAT` initialization block, add health coach state. The health coach system prompt is built once at startup and cached in `_CHAT`.

Add these imports at the top of `api/main.py` (after the existing imports):
```python
from health_coach import (
    build_system_prompt  as _hc_build_system_prompt,
    build_kg_summary     as _hc_build_kg_summary,
    check_protocol_freshness,
    HEALTH_TOOLS,
    PROTOCOL_PATH        as _HEALTH_PROTOCOL_PATH,
)
```

After the existing `_CHAT["async_client"] = ...` line, add:
```python
# ── 健康管家专项状态 ────────────────────────────────────────────
if _HEALTH_PROTOCOL_PATH.exists():
    _hc_protocol_raw = _HEALTH_PROTOCOL_PATH.read_text(encoding="utf-8")
    _hc_should_continue, _hc_stale, _hc_protocol = check_protocol_freshness(_hc_protocol_raw)
    _hc_kg_summary = _hc_build_kg_summary()
    _CHAT["health_system_prompt"] = _hc_build_system_prompt(_hc_kg_summary, _hc_protocol, _hc_stale)
else:
    _CHAT["health_system_prompt"] = _CHAT["system_prompt"]  # fallback
_CHAT["health_tools"] = HEALTH_TOOLS
```

- [ ] Read `api/main.py` to see exact insertion point
- [ ] Add the imports
- [ ] Add the health coach initialization block
- [ ] Run: `cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰 && env $(cat .env | xargs) python3 -c "from api.main import app; print('OK')"` — expect `OK`
- [ ] Commit: `git add api/main.py && git commit -m "feat: initialize health coach state at API startup"`

---

### Task B3: Route health_coach npcId in chat.py

**Files:**
- Modify: `api/routes/chat.py`

Currently the chat route resolves `resolved_prompt` based on `is_private`. Extend to also check `req.npcId`.

Find this block in `chat.py`:
```python
_PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
is_private = bool(_PRIVATE_KEY) and hmac.compare_digest(req.privateKey, _PRIVATE_KEY)
resolved_prompt = (
    _state.get("system_prompt_private", _state["system_prompt"])
    if is_private
    else _state.get("system_prompt_public", _state["system_prompt"])
)
```

Replace with:
```python
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
```

Then in the `event_stream()` function, pass `tools_override` when calling `process_message`:

Find:
```python
async for token in process_message(req.message, system_prompt_override=resolved_prompt):
```

Replace with:
```python
async for token in process_message(
    req.message,
    system_prompt_override=resolved_prompt,
    tools_override=resolved_tools,
):
```

- [ ] Read `api/routes/chat.py` to confirm exact text before editing
- [ ] Replace the prompt resolution block
- [ ] Update the `process_message` call to pass `tools_override`
- [ ] Run: `env $(cat /Users/minghan/Desktop/知识蒸馏/元宝-明翰/.env | xargs) python3 -c "from api.main import app; print('OK')"` from project root — expect `OK`
- [ ] Commit: `git add api/routes/chat.py && git commit -m "feat: route health_coach npcId to dedicated system prompt and read-only tools"`

---

### Final check

- [ ] Start server: `env $(cat .env | xargs) python3 -m uvicorn api.main:app --port 8000`
- [ ] Curl health: `curl -s http://localhost:8000/api/health` → `{"status":"ok"}`
- [ ] Confirm no import errors in server startup output
- [ ] Report: startup output, any errors
