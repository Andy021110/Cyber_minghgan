# 后端开发上下文（供 Agent 4 后端 / WorkBuddy 后端任务使用）

> 本文件摘录自 TECH_SPEC.md，覆盖 FastAPI 后端开发所需的全部规格。

---

## MVP 范围与约束

- **单用户 Mode A**：不需要 session、不需要用户表、不需要 auth 中间件
- KG 路径固定为本地文件，FastAPI 启动后直接可用
- **I/O 解耦是 FastAPI 封装的前置条件**，必须先完成再写路由
- **绝对禁止**在 FastAPI handler 里直接调用含 `input()` 的函数

---

## 后端现状与改动范围

| 组件 | 现状 | 所需改动 |
|------|------|---------|
| `CyberBrainStore` | `__init__` 已接受 `kg_path` 参数 | **无需改动** |
| `handle_review()` / `handle_kg()` / `handle_prune()` | 直接调用 `input()` / `print()` | **I/O 解耦**：提取纯函数，去掉所有 input/print |
| `decision_log.py` | 路径为模块级硬编码常量（第 33–37 行） | **参数化**：改为函数参数，保留默认值 |
| `run()` 主 REPL 循环 | 含 `input()` 交互 | **拆分**：提取 `process_message()` 异步生成器 |

---

## B1：decision_log.py 路径参数化

**改动**：将第 33–37 行的路径常量改为所有读写函数的可选参数 `logs_dir: Path = LOGS_DIR`。

**验收**：不传参数时行为与之前完全一致（向后兼容）。

---

## B2：handle_review() I/O 解耦

在 `cyber_planner.py` 中新增以下纯函数：

```python
def get_review_items() -> list[dict]:
    """返回所有 status='awaiting' 的条目，无任何 input/print"""

def process_review_decision(
    item_id: str,
    decision: str,           # "approved_kg" / "approved_log" / "rejected"
    user_note: str = "",
    importance: int | None = None,
    description: str | None = None,
) -> dict:
    """执行审批决策，返回 {"success": bool, "item_id": str}，无任何 input/print"""
```

原 `handle_review()` 保留，改为调用上面两个函数 + 自己处理 input/print（CLI 行为不变）。

---

## B3：handle_kg() I/O 解耦

新增纯函数：

```python
def get_kg_nodes(layer: str | None = None, include_archived: bool = False) -> list[dict]:
def get_kg_node(node_id: str) -> dict | None:
def get_kg_graph() -> dict:  # 返回 {"nodes": [...], "links": []}
```

---

## B4：handle_prune() I/O 解耦

新增纯函数：

```python
def get_prune_candidates() -> dict:
    # 返回 {"stats": {"critical": N, "warning": N, "healthy": N}, "candidates": [...]}
    # staleness = days_since_last_access / importance

def archive_node(node_id: str, reason: str = "") -> dict:
    # 返回 {"success": bool}

def boost_node_importance(node_id: str, new_importance: int) -> dict:
    # 返回 {"success": bool, "new_importance": int}
```

---

## B5：process_message() 提取

从 `run()` 提取异步生成器：

```python
async def process_message(user_input: str) -> AsyncGenerator[str, None]:
    """
    处理一条用户消息，流式 yield token 字符串。
    对话历史维护在 CyberBrainStore 实例内存中（单用户 MVP）。
    反刍触发时额外 yield 特殊标记：yield "[REFLECTION_TRIGGERED]"
    """
```

FastAPI 路由层负责识别 `"[REFLECTION_TRIGGERED]"` 标记，将其转为 SSE `{"type": "reflection", "triggered": true}` 事件，该标记本身不作为 `token` 类型发送。

---

## B6：FastAPI 骨架

**文件**：`api/main.py`、`api/schemas.py`

**验收**：
- `uvicorn api.main:app --reload --port 8000` 正常启动
- `GET /api/health` 返回 `{"status": "ok"}`
- CORS 允许 `http://localhost:3000`

**Pydantic 模型（api/schemas.py）**：

```python
class KGNode(BaseModel):
    id: str
    label: str
    layer: str          # "Id" | "Ego" | "Superego"
    description: str
    importance: int     # 1–10
    evidence: list[str]
    createdAt: str
    lastAccessed: str
    archived: bool
    archiveReason: str | None

class ReviewItem(BaseModel):
    id: str
    pendingId: str
    timestamp: str
    sourceMode: str     # "health" | "study" | "work" | "cyber"
    content: str
    rawEvidence: str
    proposedRoute: str  # "kg" | "log"
    proposedLayer: str | None
    aiRationale: str
    importance: int | None
    importanceNote: str | None

class Notification(BaseModel):
    id: str
    timestamp: str
    type: str           # "pending_ready" | "protocol_updated"
    message: str

class PruneCandidate(BaseModel):
    node: KGNode
    stalenessScore: float
    severity: str       # "critical" | "warning" | "healthy"
```

---

## 全部 API 接口契约

### 基础规范

| 项目 | 规范 |
|------|------|
| URL 前缀 | 所有接口 `/api` 开头 |
| 数据格式 | JSON，`Content-Type: application/json` |
| 流式响应 | SSE，`Content-Type: text/event-stream` |
| 错误格式 | `{ "error": "描述" }`，4xx/5xx |
| 启动命令 | `uvicorn api.main:app --reload --port 8000` |

---

### /api/chat

**POST /api/chat**

请求体：`{ "npcId": "cyber_minghan", "message": "你好" }`

响应（SSE 流）：
```
data: {"type": "token", "content": "你"}
data: {"type": "token", "content": "好"}
data: {"type": "done", "fullText": "你好，我是赛博明翰。"}
data: {"type": "reflection", "triggered": false}
```

**DELETE /api/chat/history** → `{ "cleared": true }`

---

### /api/review

**GET /api/review/items** → `{ "items": [ReviewItem], "count": N }`

`sourceMode` → 展示标签映射：
- `"health"` → `[健身房]`
- `"work"` → `[办公室]`
- `"study"` → `[学习室]`
- `"cyber"` → `[赛博明翰]`

**GET /api/review/count** → `{ "count": N }`

**POST /api/review/items/{item_id}/decide**

请求体：
```json
{
  "decision": "approved_kg",
  "userNote": "可选",
  "importance": 7,
  "description": "可选，仅 approved_kg"
}
```
响应：`{ "success": true, "itemId": "..." }`

---

### /api/kg

**GET /api/kg/nodes?layer=Ego&includeArchived=false** → `{ "nodes": [KGNode], "count": N }`

**GET /api/kg/nodes/{node_id}** → 单个 KGNode，不存在返回 404

**GET /api/kg/graph** → `{ "nodes": [{id, label, layer, importance}], "links": [] }`（links 暂为空数组）

---

### /api/prune

**GET /api/prune/candidates** → `{ "stats": {critical, warning, healthy}, "candidates": [PruneCandidate] }`

**POST /api/prune/{node_id}/archive** 请求体：`{ "reason": "..." }` → `{ "success": true }`

**POST /api/prune/{node_id}/boost** 请求体：`{ "newImportance": 8 }` → `{ "success": true, "newImportance": 8 }`

---

### /api/notifications

**GET /api/notifications** → `{ "notifications": [Notification], "count": N }`（只返回 consumed: false 的条目）

**POST /api/notifications/{id}/consume** → `{ "success": true }`

---

## 目录结构

```
api/
├── __init__.py
├── main.py          ← FastAPI app 实例、CORS、全局初始化
├── schemas.py       ← Pydantic 模型
└── routes/
    ├── __init__.py
    ├── chat.py
    ├── review.py
    ├── kg.py
    ├── prune.py
    └── notifications.py
```
