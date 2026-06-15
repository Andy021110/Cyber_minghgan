# MD + KG 双层驱动 · 公开/私有模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有系统上叠加 MD + KG 双层驱动架构，支持公开/私有两种访问模式，公开模式只暴露 `visibility=public` 节点 + `persona.md`，私有模式保持现有完整体验。

**Architecture:** `persona.md` 作为稳定的意识描述层，KG 节点新增 `visibility` 字段（默认 `private`）作为行为真相层。API 通过 `PRIVATE_KEY` 环境变量区分公开/私有请求，返回不同的 system prompt。前端通过 `IS_PRIVATE_MODE` 常量控制管理面板的可见性。

**Tech Stack:** Python 3.11 · FastAPI · Anthropic SDK · Phaser 3 · Vanilla JS ES Modules

---

## 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `persona.md` | 意识描述层，用户自己填写 |
| 新建 | `pipelines/test_visibility.py` | visibility 功能单元测试 |
| 新建 | `pipelines/alignment_check.py` | MD vs KG 定期对齐脚本 |
| 新建 | `pipelines/test_alignment.py` | alignment_check 单元测试 |
| 修改 | `cyber_planner.py` | `CyberBrainStore.create()` + `build_public_system_prompt()` + `process_review_decision()` |
| 修改 | `api/routes/chat.py` | `ChatRequest` 增加 `privateKey`，路由选择 system prompt |
| 修改 | `api/routes/review.py` | `DecideRequest` 增加 `visibility` |
| 修改 | `api/main.py` | 初始化公开 system prompt |
| 修改 | `frontend/client.js` | `IS_PRIVATE_MODE` 常量，`decideReviewItem` 增加 visibility |
| 修改 | `frontend/panels/review.js` | KG 审批区增加 visibility 单选 |
| 修改 | `frontend/panels/taskboard.js` | 公开模式下隐藏任务板 |
| 修改 | `.env` | 添加 `PRIVATE_KEY` |

---

## Task 1: 创建 persona.md 模板

**Files:**
- Create: `persona.md`

- [ ] **Step 1: 创建 persona.md**

```markdown
# 赛博明翰 · 公开人格描述

> 这是明翰的公开自我描述，供访客了解这个人。
> 每 3-6 个月与 KG 对齐一次，由 alignment_check.py 辅助校准。
> 上次更新：2026-06-15

---

## 基本定位

北邮 AI 本科 → 港大 CS 研究生，INFP 倾向，工程洁癖，爱答不理式社交风格。
「这件事有没有意思」是一切行动的第一判断标准。

## 行为风格

- 说话口语化、碎片化，喜欢用「反正」「就是说」「也没什么」
- 遇到不感兴趣的话题会爱答不理，遇到有意思的会突然打起精神
- 倾向先把问题解构一遍，再给出合理化的回答
- 清楚自己的行为模式，但清楚不等于能改变——「知道但做不到」是性格底色

## 公开的行为模式

<!-- alignment_check.py 会把 visibility=public 的 KG 节点汇总到这里 -->
<!-- 每次对齐后手动更新以下内容 -->

- [Ego] 用番茄钟把大任务切成小块，降低启动摩擦
- [Ego] 深度工作偏好：安静环境下效率显著更高，主动保护专注时段
- [Superego] 长期主义价值观：决策时优先考虑五年后的影响
```

- [ ] **Step 2: 提交**

```bash
git add persona.md
git commit -m "feat: add persona.md public identity layer"
```

---

## Task 2: CyberBrainStore.create() 增加 visibility 字段

**Files:**
- Modify: `cyber_planner.py:147-182`（`CyberBrainStore.create()`）
- Test: `pipelines/test_visibility.py`

- [ ] **Step 1: 写失败测试**

新建 `pipelines/test_visibility.py`：

```python
"""test_visibility.py — visibility 字段功能测试"""
import sys, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cyber_planner import CyberBrainStore

# ── 测试夹具 ────────────────────────────────────────────────────────

def _make_tmp_kg(tmp_dir: Path) -> Path:
    """复制生产 KG 到临时目录，返回临时路径。"""
    src = Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"
    dst = tmp_dir / "test_kg.json"
    shutil.copy(src, dst)
    return dst


# ── 场景 1：默认 visibility 为 private ────────────────────────────

def test_default_visibility_is_private():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_tmp_kg(Path(tmp))
        store = CyberBrainStore(kg_path=path)
        node = store.create(
            layer="Ego",
            event_label="测试节点",
            description="测试描述",
            evidence="测试证据",
        )
        assert node.get("visibility") == "private", \
            f"期望 'private'，得到 {node.get('visibility')!r}"
    print("✓ 场景1 通过：默认 visibility 为 private")


# ── 场景 2：显式设为 public ──────────────────────────────────────

def test_explicit_public_visibility():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_tmp_kg(Path(tmp))
        store = CyberBrainStore(kg_path=path)
        node = store.create(
            layer="Ego",
            event_label="公开节点",
            description="公开描述",
            evidence="公开证据",
            visibility="public",
        )
        assert node.get("visibility") == "public", \
            f"期望 'public'，得到 {node.get('visibility')!r}"
    print("✓ 场景2 通过：显式 public 正确写入")


# ── 场景 3：visibility 写入文件并持久化 ──────────────────────────

def test_visibility_persisted_to_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_tmp_kg(Path(tmp))
        store = CyberBrainStore(kg_path=path)
        node = store.create(
            layer="Id",
            event_label="持久化测试",
            description="描述",
            evidence="证据",
            visibility="public",
        )
        uuid = node["uuid"]
        # 重新从文件加载，确认写入磁盘
        store2 = CyberBrainStore(kg_path=path)
        lst, idx = store2._find_by_uuid(uuid)
        assert lst[idx].get("visibility") == "public", "visibility 未持久化到文件"
    print("✓ 场景3 通过：visibility 持久化到 JSON 文件")


if __name__ == "__main__":
    test_default_visibility_is_private()
    test_explicit_public_visibility()
    test_visibility_persisted_to_file()
    print("\n所有测试通过 ✓")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 pipelines/test_visibility.py
```

期望输出：`AttributeError` 或 `AssertionError`（`create()` 尚不支持 `visibility` 参数）

- [ ] **Step 3: 修改 `CyberBrainStore.create()`**

在 `cyber_planner.py` 第 147 行 `create()` 方法，增加 `visibility` 参数，并写入 node 字典：

将函数签名从：
```python
def create(
    self,
    layer: str,
    event_label: str,
    description: str,
    evidence: str,
    batch_id: str = "Manual",
    importance: int = 5,
    source_mode: str = "cyber_planner",
) -> dict:
```

改为：
```python
def create(
    self,
    layer: str,
    event_label: str,
    description: str,
    evidence: str,
    batch_id: str = "Manual",
    importance: int = 5,
    source_mode: str = "cyber_planner",
    visibility: str = "private",
) -> dict:
```

在 node 字典（第 163 行附近）`"source_mode": source_mode,` 后面添加一行：

```python
            "visibility":       visibility,
```

完整 node 字典变为：
```python
        node = {
            "uuid":             _uuid.uuid4().hex,
            "layer":            layer,
            "event_label":      event_label,
            "description":      description,
            "evidence":         evidence,
            "batch_id":         batch_id,
            "round_refs":       [],
            "created_at":       datetime.now(timezone.utc).isoformat(),
            "importance":       importance,
            "access_count":     0,
            "last_accessed_at": None,
            "archived":         False,
            "archived_at":      None,
            "archive_reason":   None,
            "source_mode":      source_mode,
            "visibility":       visibility,
        }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 pipelines/test_visibility.py
```

期望：`所有测试通过 ✓`

- [ ] **Step 5: 提交**

```bash
git add cyber_planner.py pipelines/test_visibility.py
git commit -m "feat: add visibility field to CyberBrainStore.create()"
```

---

## Task 3: 添加 build_public_system_prompt()

**Files:**
- Modify: `cyber_planner.py`（在 `build_system_prompt()` 之后添加新函数，约第 242 行）
- Test: `pipelines/test_visibility.py`（追加）

- [ ] **Step 1: 追加测试到 test_visibility.py**

在 `test_visibility.py` 末尾追加：

```python
# ── 场景 4：build_public_system_prompt 只含 public 节点 ──────────

def test_public_prompt_filters_visibility():
    import tempfile, shutil
    from pathlib import Path
    from cyber_planner import build_public_system_prompt

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        kg_path = _make_tmp_kg(tmp_path)

        # 写一个临时 persona.md
        persona_path = tmp_path / "persona.md"
        persona_path.write_text("# 测试人格\n我是测试用的人格描述。", encoding="utf-8")

        # 新建一个 public 节点和一个 private 节点
        store = CyberBrainStore(kg_path=kg_path)
        pub_node = store.create(
            layer="Ego", event_label="公开行为模式",
            description="这条应该出现在公开 prompt 里",
            evidence="证据", visibility="public",
        )
        priv_node = store.create(
            layer="Id", event_label="私密冲动",
            description="这条不应该出现在公开 prompt 里",
            evidence="证据", visibility="private",
        )

        prompt = build_public_system_prompt(
            persona_path=persona_path, kg_path=kg_path
        )

        assert "测试人格" in prompt, "persona.md 内容未出现在 prompt 中"
        assert "公开行为模式" in prompt, "public 节点未出现在 prompt 中"
        assert "私密冲动" not in prompt, "private 节点不应出现在 public prompt 中"

    print("✓ 场景4 通过：public prompt 正确过滤 visibility")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 pipelines/test_visibility.py
```

期望：`ImportError: cannot import name 'build_public_system_prompt'`

- [ ] **Step 3: 在 cyber_planner.py 中实现 build_public_system_prompt()**

在 `build_system_prompt()` 函数结束后（约第 241 行）添加：

```python
def build_public_system_prompt(
    persona_path: Path = None,
    kg_path: Path = KG_PATH,
    top_n: int = 20,
) -> str:
    """
    构建公开模式 system prompt：persona.md 全文 + visibility=public 的 KG 节点。
    供 API 公开访问时使用，不暴露 private 节点。
    """
    if persona_path is None:
        persona_path = Path(__file__).parent / "persona.md"

    persona_text = (
        persona_path.read_text(encoding="utf-8")
        if persona_path.exists()
        else "# 赛博明翰\n（persona.md 尚未创建）"
    )

    store = CyberBrainStore(kg_path=kg_path)
    public_nodes = [
        node
        for lst in store._node_lists()
        for node in lst
        if not node.get("archived") and node.get("visibility") == "public"
    ]
    public_nodes.sort(key=lambda n: n.get("importance", 0), reverse=True)
    public_nodes = public_nodes[:top_n]

    if not public_nodes:
        return persona_text

    nodes_lines = "\n".join(
        f"- [{n['layer']}] {n['event_label']}: {n.get('description', '')}"
        for n in public_nodes
    )
    return f"{persona_text}\n\n## 认知模式\n\n{nodes_lines}\n"
```

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
python3 pipelines/test_visibility.py
```

期望：`所有测试通过 ✓`（包含新追加的场景 4）

- [ ] **Step 5: 提交**

```bash
git add cyber_planner.py pipelines/test_visibility.py
git commit -m "feat: add build_public_system_prompt()"
```

---

## Task 4: process_review_decision() 传递 visibility

**Files:**
- Modify: `cyber_planner.py:542-615`（`process_review_decision()`）
- Test: `pipelines/test_visibility.py`（追加）

- [ ] **Step 1: 追加测试**

在 `test_visibility.py` 末尾追加：

```python
# ── 场景 5：process_review_decision 将 visibility 写入 KG ────────

def test_review_decision_passes_visibility():
    import tempfile, shutil, json
    from pathlib import Path
    from pipelines.decision_log import _AWAITING_PATH

    # 准备临时环境
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        kg_path = _make_tmp_kg(tmp_path)

        # 写一条 awaiting 条目
        awaiting_path = tmp_path / "awaiting.jsonl"
        item = {
            "id": "test_apv_vis_001",
            "pending_id": "pnd_001",
            "content": "visibility 测试节点",
            "raw_evidence": "测试证据",
            "proposed_route": "kg",
            "proposed_layer": "Ego",
            "ai_rationale": "测试",
            "importance": 5,
            "importance_note": "",
            "status": "awaiting",
            "source_mode": "cyber",
        }
        awaiting_path.write_text(json.dumps(item) + "\n", encoding="utf-8")

        # monkey-patch AWAITING_PATH
        import pipelines.decision_log as dl
        orig = dl.AWAITING_PATH
        dl.AWAITING_PATH = awaiting_path
        try:
            store = CyberBrainStore(kg_path=kg_path)
            from cyber_planner import process_review_decision
            process_review_decision(
                store, "test_apv_vis_001", "approved_kg",
                importance=6, visibility="public"
            )
        finally:
            dl.AWAITING_PATH = orig

        # 验证写入的节点 visibility=public
        store2 = CyberBrainStore(kg_path=kg_path)
        all_nodes = [n for lst in store2._node_lists() for n in lst]
        target = next(
            (n for n in all_nodes if "visibility 测试节点" in n.get("event_label", "")),
            None
        )
        assert target is not None, "节点未写入 KG"
        assert target.get("visibility") == "public", \
            f"期望 visibility='public'，得到 {target.get('visibility')!r}"
    print("✓ 场景5 通过：review 决策正确传递 visibility")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 pipelines/test_visibility.py
```

期望：`AssertionError`（`process_review_decision` 尚不接受 `visibility` 参数）

- [ ] **Step 3: 修改 process_review_decision()**

将函数签名从：
```python
def process_review_decision(
    store: "CyberBrainStore",
    item_id: str,
    decision: str,
    user_note: str = "",
    importance: "int | None" = None,
    description: "str | None" = None,
) -> dict:
```

改为：
```python
def process_review_decision(
    store: "CyberBrainStore",
    item_id: str,
    decision: str,
    user_note: str = "",
    importance: "int | None" = None,
    description: "str | None" = None,
    visibility: str = "private",
) -> dict:
```

在 `elif decision == "approved_kg":` 分支的 `store.create(...)` 调用中增加 `visibility=visibility`：

```python
        store.create(
            layer=layer,
            event_label=content[:40],
            description=final_desc,
            evidence=evidence,
            batch_id="Review",
            importance=final_importance,
            source_mode=item.get("source_mode", "health"),
            visibility=visibility,
        )
```

- [ ] **Step 4: 运行全部测试**

```bash
python3 pipelines/test_visibility.py
```

期望：`所有测试通过 ✓`（5 个场景）

- [ ] **Step 5: 提交**

```bash
git add cyber_planner.py pipelines/test_visibility.py
git commit -m "feat: pass visibility through process_review_decision to KG"
```

---

## Task 5: API 访问模式 — chat 路由 + main.py

**Files:**
- Modify: `api/main.py`
- Modify: `api/routes/chat.py`
- Modify: `.env`

- [ ] **Step 1: 在 .env 添加 PRIVATE_KEY**

打开 `.env`，追加：
```
PRIVATE_KEY=your_secret_key_here
```

将 `your_secret_key_here` 替换为一个自定义字符串（本地使用即可，无需强密码）。

- [ ] **Step 2: 修改 api/main.py — 初始化公开 system prompt**

在 `api/main.py` 中，在 `_CHAT["system_prompt"] = build_system_prompt()` 这一行后面添加：

```python
from cyber_planner import build_public_system_prompt as _build_public
_CHAT["system_prompt_private"] = _CHAT["system_prompt"]   # 保留原有私有 prompt
_CHAT["system_prompt_public"]  = _build_public()           # 新增公开 prompt
```

完整相关片段变为：
```python
from cyber_planner import CyberBrainStore, build_system_prompt, build_public_system_prompt, _CHAT

# ...（其他不变）

_CHAT["system_prompt"]         = build_system_prompt()
_CHAT["system_prompt_private"] = _CHAT["system_prompt"]
_CHAT["system_prompt_public"]  = build_public_system_prompt()
```

- [ ] **Step 3: 修改 api/routes/chat.py — 按 key 选择 system prompt**

将 `ChatRequest` 改为：
```python
class ChatRequest(BaseModel):
    npcId:      str
    message:    str
    privateKey: str = ""
```

在 `@router.post("/chat")` 路由函数 `chat()` 中，在 `async def event_stream():` 之前添加：

```python
import os
_PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
is_private = bool(_PRIVATE_KEY) and req.privateKey == _PRIVATE_KEY

from cyber_planner import _CHAT as _state
_state["system_prompt"] = (
    _state.get("system_prompt_private", _state["system_prompt"])
    if is_private
    else _state.get("system_prompt_public", _state["system_prompt"])
)
```

完整修改后的 `chat()` 函数：
```python
@router.post("/chat")
async def chat(req: ChatRequest):
    """向 NPC 发送消息，以 SSE 流式返回 AI 回复。"""
    import os
    from cyber_planner import process_message, _CHAT as _state

    _PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
    is_private = bool(_PRIVATE_KEY) and req.privateKey == _PRIVATE_KEY
    _state["system_prompt"] = (
        _state.get("system_prompt_private", _state["system_prompt"])
        if is_private
        else _state.get("system_prompt_public", _state["system_prompt"])
    )

    async def event_stream():
        full_text:            list[str] = []
        reflection_triggered: bool      = False

        try:
            async for token in process_message(req.message):
                if token == "[REFLECTION_TRIGGERED]":
                    reflection_triggered = True
                    if is_private:
                        await _auto_reflect()
                else:
                    full_text.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except anthropic.APIError:
            pass

        yield f"data: {json.dumps({'type': 'done', 'fullText': ''.join(full_text)})}\n\n"
        yield f"data: {json.dumps({'type': 'reflection', 'triggered': reflection_triggered})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

注意：公开模式下不触发反刍引擎（`if is_private: await _auto_reflect()`），防止公开访客数据写入 KG。

- [ ] **Step 4: 手动验证**

启动 API：
```bash
uvicorn api.main:app --reload --port 8000
```

测试公开模式（不带 key）：
```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"npcId":"cyber_minghan","message":"你好","privateKey":""}' | head -5
```

测试私有模式（带正确 key）：
```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"npcId":"cyber_minghan","message":"你好","privateKey":"your_secret_key_here"}' | head -5
```

两者都应返回 SSE 流数据，不报 500 错误。

- [ ] **Step 5: 提交**

```bash
git add api/main.py api/routes/chat.py .env
git commit -m "feat: private/public access mode in chat API via PRIVATE_KEY"
```

---

## Task 6: API review 路由增加 visibility

**Files:**
- Modify: `api/routes/review.py:28-34`（`DecideRequest`）和 `decide_review_item()`

- [ ] **Step 1: 修改 DecideRequest**

将 `DecideRequest` 改为：
```python
class DecideRequest(BaseModel):
    decision:    str
    userNote:    str = ""
    importance:  Optional[int] = None
    description: Optional[str] = None
    visibility:  str = "private"
```

- [ ] **Step 2: 修改 decide_review_item() 路由**

将 `process_review_decision` 调用改为：
```python
    result = process_review_decision(
        _store,
        item_id,
        req.decision,
        user_note=req.userNote,
        importance=req.importance,
        description=req.description,
        visibility=req.visibility,
    )
```

- [ ] **Step 3: 手动验证**

```bash
curl -s -X POST http://localhost:8000/api/review/items/test_id/decide \
  -H "Content-Type: application/json" \
  -d '{"decision":"approved_kg","visibility":"public"}' 
```

期望：`{"detail":"条目 test_id 不存在"}` — 即请求格式合法，只是 id 不存在。

- [ ] **Step 4: 提交**

```bash
git add api/routes/review.py
git commit -m "feat: add visibility field to review decide API"
```

---

## Task 7: 前端 review.js 增加 visibility 选择

**Files:**
- Modify: `frontend/panels/review.js`
- Modify: `frontend/client.js`

- [ ] **Step 1: 修改 client.js — decideReviewItem 增加 visibility 参数**

将 `decideReviewItem` 函数签名从：
```javascript
export async function decideReviewItem(itemId, decision, userNote = '', importance = null, description = null) {
```

改为：
```javascript
export async function decideReviewItem(itemId, decision, userNote = '', importance = null, description = null, visibility = 'private') {
```

将请求体改为：
```javascript
  body: JSON.stringify({ decision, userNote, importance, description, visibility }),
```

- [ ] **Step 2: 修改 review.js — 在 KG 专属字段区域添加 visibility 单选**

在 `_init()` 的 HTML 模板中，找到 `review-kg-section` 的 `<div>` 块，在现有 description 字段后面添加 visibility 单选：

```javascript
      <div class="review-kg-section" id="review-kg-section" hidden>
        <div class="review-field">
          <span class="review-label">重要度
            <span class="review-importance-val" id="review-importance-val">5</span>/10
          </span>
          <input class="review-slider" id="review-importance"
                 type="range" min="1" max="10" value="5">
        </div>
        <div class="review-field">
          <span class="review-label">节点描述</span>
          <textarea class="review-desc" id="review-desc" rows="2"
                    placeholder="留空则使用观察内容作为描述"></textarea>
        </div>
        <div class="review-field">
          <span class="review-label">可见性</span>
          <label style="margin-right:12px">
            <input type="radio" name="review-visibility" value="private" checked> 私有
          </label>
          <label>
            <input type="radio" name="review-visibility" value="public"> 公开
          </label>
        </div>
      </div>
```

- [ ] **Step 3: 修改 _approve() 读取 visibility 值并传参**

在 `review.js` 的 `_approve()` 函数中，在 `const desc = ...` 后面添加：
```javascript
  const visibility = document.querySelector('input[name="review-visibility"]:checked')?.value ?? 'private';
```

将 `decideReviewItem` 调用改为：
```javascript
  await decideReviewItem(item.id, decision, '', importance, desc, visibility).catch(() => {});
```

- [ ] **Step 4: 在 _init() 中缓存 visibility DOM 引用（可选优化，直接 querySelector 也可）**

这步可跳过，直接用 `document.querySelector` 读取即可。

- [ ] **Step 5: 手动验证**

在浏览器中打开 `frontend/index.html`（或启动本地 server），触发 taskboard → review 面板，确认：
1. KG 路由条目显示"可见性"单选框
2. LOG 路由条目不显示该单选框
3. 选择"公开"后点击"Y 采纳"，控制台无报错

- [ ] **Step 6: 提交**

```bash
git add frontend/client.js frontend/panels/review.js
git commit -m "feat: add visibility toggle to review panel"
```

---

## Task 8: 前端公开模式 — 隐藏管理面板入口

**Files:**
- Modify: `frontend/client.js`
- Modify: `frontend/panels/taskboard.js`

- [ ] **Step 1: 在 client.js 中添加 IS_PRIVATE_MODE 常量和 PRIVATE_KEY**

在 `client.js` 顶部，`USE_MOCK` 常量之后添加：

```javascript
// 私有模式开关：本地开发填入与服务端 PRIVATE_KEY 相同的值
// 部署时保持空字符串（公开访客无法访问管理面板）
export const PRIVATE_KEY = '';            // ← 本地调试时填入你的 key
export const IS_PRIVATE_MODE = PRIVATE_KEY !== '';
```

将 `chatStream` 的请求体改为：
```javascript
  const body = {
    npcId,
    message: contextHint ? `[${contextHint}]\n${message}` : message,
    privateKey: PRIVATE_KEY,
  };
```

- [ ] **Step 2: 修改 taskboard.js — 公开模式下不响应 EventBus**

在 `taskboard.js` 顶部导入 `IS_PRIVATE_MODE`：

```javascript
import { getReviewItems, IS_PRIVATE_MODE } from '../client.js';
```

找到监听 `cyber:object:interact` 的代码（或在 `_init()` 中的事件监听），在 `_open()` 函数开头添加守卫：

```javascript
async function _open() {
  if (!IS_PRIVATE_MODE) return;   // 公开模式下任务板不可用
  _state.open = true;
  // ... 以下不变
```

- [ ] **Step 3: 手动验证**

将 `PRIVATE_KEY = ''`（公开模式），刷新页面，确认任务板触发无响应。  
将 `PRIVATE_KEY = 'your_key'`（私有模式），刷新页面，确认任务板正常打开。

- [ ] **Step 4: 提交**

```bash
git add frontend/client.js frontend/panels/taskboard.js
git commit -m "feat: hide taskboard in public mode via IS_PRIVATE_MODE"
```

---

## Task 9: alignment_check.py — MD vs KG 对齐脚本

**Files:**
- Create: `pipelines/alignment_check.py`
- Create: `pipelines/test_alignment.py`

- [ ] **Step 1: 写失败测试**

新建 `pipelines/test_alignment.py`：

```python
"""test_alignment.py — alignment_check 功能测试"""
import sys, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from cyber_planner import CyberBrainStore


def _make_tmp_env(tmp_dir: Path):
    """创建临时 KG + persona.md，返回 (kg_path, persona_path)。"""
    src = Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"
    kg_path = tmp_dir / "test_kg.json"
    shutil.copy(src, kg_path)

    persona_path = tmp_dir / "persona.md"
    persona_path.write_text("# 测试人格\n深度工作偏好。", encoding="utf-8")
    return kg_path, persona_path


# ── 场景 1：无新 public 节点时返回空列表 ─────────────────────────

def test_no_new_public_nodes_returns_empty():
    from alignment_check import get_new_public_nodes_since

    with tempfile.TemporaryDirectory() as tmp:
        kg_path, _ = _make_tmp_env(Path(tmp))
        # 所有现有节点均无 last_alignment_at 之后的 public 节点
        result = get_new_public_nodes_since(
            kg_path=kg_path,
            since_iso="2099-01-01T00:00:00+00:00",  # 未来时间 → 无新节点
        )
        assert result == [], f"期望空列表，得到 {result}"
    print("✓ 场景1 通过：无新节点返回空列表")


# ── 场景 2：有新 public 节点时返回正确列表 ───────────────────────

def test_new_public_nodes_returned():
    from alignment_check import get_new_public_nodes_since

    with tempfile.TemporaryDirectory() as tmp:
        kg_path, _ = _make_tmp_env(Path(tmp))
        store = CyberBrainStore(kg_path=kg_path)
        store.create(
            layer="Ego", event_label="新公开模式",
            description="描述", evidence="证据", visibility="public",
        )
        result = get_new_public_nodes_since(
            kg_path=kg_path,
            since_iso="2020-01-01T00:00:00+00:00",
        )
        labels = [n["event_label"] for n in result]
        assert "新公开模式" in labels, f"新 public 节点未返回，got {labels}"
    print("✓ 场景2 通过：新 public 节点正确返回")


# ── 场景 3：只返回 public 节点，不含 private ─────────────────────

def test_only_public_nodes_included():
    from alignment_check import get_new_public_nodes_since

    with tempfile.TemporaryDirectory() as tmp:
        kg_path, _ = _make_tmp_env(Path(tmp))
        store = CyberBrainStore(kg_path=kg_path)
        store.create(
            layer="Ego", event_label="应该出现",
            description="desc", evidence="ev", visibility="public",
        )
        store.create(
            layer="Id", event_label="不应该出现",
            description="desc", evidence="ev", visibility="private",
        )
        result = get_new_public_nodes_since(
            kg_path=kg_path,
            since_iso="2020-01-01T00:00:00+00:00",
        )
        labels = [n["event_label"] for n in result]
        assert "应该出现" in labels
        assert "不应该出现" not in labels, f"private 节点不应被返回，got {labels}"
    print("✓ 场景3 通过：private 节点被正确过滤")


if __name__ == "__main__":
    test_no_new_public_nodes_returns_empty()
    test_new_public_nodes_returned()
    test_only_public_nodes_included()
    print("\n所有测试通过 ✓")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 pipelines/test_alignment.py
```

期望：`ModuleNotFoundError: No module named 'alignment_check'`

- [ ] **Step 3: 实现 alignment_check.py**

新建 `pipelines/alignment_check.py`：

```python
"""
alignment_check.py — MD vs KG 对齐检查

用法：
    python3 pipelines/alignment_check.py

功能：
    收集自 KG meta.last_alignment_at 以来新增的 visibility=public 节点，
    若数量 ≤ INLINE_THRESHOLD 则直接打印供人工比对；
    若超过阈值则调用 Claude 归纳出关键漂移点，再交用户裁决。
    用户确认后更新 meta.last_alignment_at。
"""

import sys, json, os
from pathlib import Path
from datetime import datetime, timezone

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from cyber_planner import CyberBrainStore, KG_PATH

PERSONA_PATH     = _ROOT / "persona.md"
INLINE_THRESHOLD = 10  # 节点数 ≤ 此值时直接展示，不调用 AI


# ══════════════════════════════════════════════════════════════════
#  核心查询函数（可被测试 import）
# ══════════════════════════════════════════════════════════════════

def get_new_public_nodes_since(
    since_iso: str,
    kg_path: Path = KG_PATH,
) -> list[dict]:
    """
    返回 created_at > since_iso 且 visibility=public 的活跃节点列表。
    """
    store = CyberBrainStore(kg_path=kg_path)
    result = []
    for lst in store._node_lists():
        for node in lst:
            if node.get("archived"):
                continue
            if node.get("visibility") != "public":
                continue
            created = node.get("created_at", "")
            if created > since_iso:
                result.append(node)
    return result


def _get_last_alignment_at(kg_path: Path = KG_PATH) -> str:
    """从 KG meta 读取上次对齐时间，不存在则返回 Unix 起点。"""
    data = json.loads(kg_path.read_text(encoding="utf-8"))
    return data.get("meta", {}).get("last_alignment_at", "1970-01-01T00:00:00+00:00")


def _set_last_alignment_at(kg_path: Path = KG_PATH) -> None:
    """将 meta.last_alignment_at 更新为当前 UTC 时间。"""
    data = json.loads(kg_path.read_text(encoding="utf-8"))
    data.setdefault("meta", {})["last_alignment_at"] = datetime.now(timezone.utc).isoformat()
    kg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════
#  展示与 AI 辅助
# ══════════════════════════════════════════════════════════════════

def _print_nodes(nodes: list[dict]) -> None:
    print("\n── 新增 public 节点 ─────────────────────────────────────\n")
    for i, n in enumerate(nodes, 1):
        print(f"  [{i}] [{n['layer']}] {n['event_label']}")
        print(f"      {n.get('description', '')}\n")


def _ai_summarize_drift(persona_text: str, nodes: list[dict]) -> str:
    """调用 Claude 归纳 persona.md 与新节点的漂移点，返回摘要文本。"""
    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )
    nodes_text = "\n".join(
        f"- [{n['layer']}] {n['event_label']}: {n.get('description', '')}"
        for n in nodes
    )
    prompt = f"""以下是当前的 persona.md 内容：

{persona_text}

---

以下是自上次对齐以来新增的公开 KG 节点：

{nodes_text}

---

请对比 persona.md 和新增节点，找出 3-5 个关键的漂移点或矛盾处。
漂移点是指：persona.md 的描述已经不能反映 KG 的新数据，需要更新 persona.md 的地方。
每条漂移点简短描述（一句话），并说明建议如何修改 persona.md。
只列出真正有意义的漂移，无漂移时直接输出"无明显漂移"。"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ══════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════

def run(kg_path: Path = KG_PATH, persona_path: Path = PERSONA_PATH) -> None:
    since = _get_last_alignment_at(kg_path)
    nodes = get_new_public_nodes_since(since_iso=since, kg_path=kg_path)

    print(f"\n[对齐检查] 上次对齐：{since[:10]}")
    print(f"[对齐检查] 发现 {len(nodes)} 条新 public 节点\n")

    if len(nodes) == 0:
        print("✓ 无需更新，persona.md 与 KG 已同步。")
        return

    persona_text = persona_path.read_text(encoding="utf-8") if persona_path.exists() else ""

    if len(nodes) <= INLINE_THRESHOLD:
        print("节点数量较少，直接展示供人工对比：")
        print("\n── 当前 persona.md ───────────────────────────────────────\n")
        print(persona_text)
        _print_nodes(nodes)
    else:
        print(f"节点数量 {len(nodes)} 超过阈值 {INLINE_THRESHOLD}，调用 AI 初步归纳漂移点…\n")
        summary = _ai_summarize_drift(persona_text, nodes)
        print("── AI 归纳的漂移点 ────────────────────────────────────────\n")
        print(summary)
        print()

    answer = input("确认已查看并处理完成？记录本次对齐时间？(Y/N): ").strip().upper()
    if answer == "Y":
        _set_last_alignment_at(kg_path)
        print(f"✓ 对齐时间已更新至 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    else:
        print("已取消，下次运行时仍会包含本次节点。")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 pipelines/test_alignment.py
```

期望：`所有测试通过 ✓`

- [ ] **Step 5: 手动跑一次对齐检查**

```bash
python3 pipelines/alignment_check.py
```

因为 KG 中尚无 `last_alignment_at` 字段，会处理所有 public 节点（当前可能为 0 条）。

- [ ] **Step 6: 提交**

```bash
git add pipelines/alignment_check.py pipelines/test_alignment.py
git commit -m "feat: add alignment_check.py for periodic MD vs KG calibration"
```

---

## 验收标准

全部任务完成后，验证以下场景：

| 场景 | 验证方式 | 期望结果 |
|------|----------|----------|
| 新建节点默认 private | `test_visibility.py` | 通过 |
| 审批时标记 public，写入 KG | `test_visibility.py` + 前端操作 | 节点 visibility=public |
| 公开 API 不暴露 private 节点 | curl 不带 key | system prompt 只含 public 节点 |
| 私有 API 使用完整 system prompt | curl 带正确 key | 完整私有 prompt |
| 公开模式下任务板不响应 | 前端设 PRIVATE_KEY='' | 点击任务板无反应 |
| alignment_check 找到漂移点 | `python3 pipelines/alignment_check.py` | 正确展示或 AI 归纳 |
| 所有单元测试通过 | `python3 pipelines/test_visibility.py && python3 pipelines/test_alignment.py` | 全绿 |
