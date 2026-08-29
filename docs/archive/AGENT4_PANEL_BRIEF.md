# Agent 4：面板层 + 接口开发者 · 任务简报

> 版本：2026-06-07  
> 执行人：全栈开发者（需同时掌握 Python/FastAPI 和 HTML/CSS/JS）  
> 依赖文档：`docs/TECH_SPEC.md`

---

## 一、角色定位

**你是什么**：项目里唯一同时触碰后端和前端的人。你的工作分两条轨道：

- **后端轨道**：把现有 Python 业务逻辑从 CLI 壳子里剥出来，包一层 FastAPI，让浏览器可以调用
- **前端轨道**：实现所有 HTML/CSS 功能面板，监听 Phaser 发来的 EventBus 事件，调用后端 API，把结果展示给用户

这两条轨道大部分时间可以并行——后端没完成时，前端可以先用 mock 数据开发。

**你负责什么**：

后端：
- `decision_log.py` 路径参数化
- `handle_review()` / `handle_kg()` / `handle_prune()` 的 I/O 解耦（从 `input()`/`print()` 改为接收参数、返回数据）
- 对话核心逻辑的 I/O 解耦（从 REPL `run()` 提取 `process_message()`）
- FastAPI 应用：`api/main.py` + 五组路由（chat / review / kg / prune / notifications）
- SSE 流式输出封装

前端：
- `frontend/index.html`：入口页面，加载 Phaser 和所有面板脚本
- `frontend/style/`：CSS Token 变量、面板样式、HUD 样式
- `frontend/client.js`：所有 API 请求的 fetch 封装
- `frontend/panels/`：五个功能面板（dialogue / taskboard / review / kg / prune）
- EventBus 接收侧（监听 Phaser 事件）和发送侧（向 Phaser 发送面板状态）
- HUD 顶部栏（房间名 + 通知角标）

**你不负责什么**：
- 不写任何 Phaser 场景或游戏逻辑（Agent 3 负责）
- 不制作或修改任何美术资产（Agent 2 负责）
- 不修改 `cyber_planner.py` 的 KG 操作逻辑、反刍判断逻辑、prompt 构造逻辑——只解耦 I/O 层
- 不实现任何用户注册、登录、session 管理（MVP 单用户，不需要 auth）

**与其他 Agent 的关系**：
- 依赖 Agent 2 的 UI 设计稿还原面板样式（设计稿到位前先用骨架样式开发）
- 与 Agent 3 通过 EventBus 通信，双方无代码依赖，可独立开发测试
- Agent 1 的 TECH_SPEC 第五章是你的 API 实现规范，严格按照执行

---

## 二、启动前必读

**必读章节（TECH_SPEC.md）**：

| 章节 | 为什么要读 |
|------|-----------|
| 版本范围说明 | 明确 MVP 是单用户 Mode A，不做 auth，不做多用户 |
| 第一章 1.1、1.3、1.5 | MVP 范围、技术栈选型、CSS 色彩变量——你要写的 CSS 从这里来 |
| 第一章 1.7 | 后端现状和改动范围——最重要，明确哪些要改、哪些不能动 |
| 第二章 2.5 | 实体常量名（`sourceMode` 映射、`objectId` 列表）——面板展示标签的依据 |
| 第三章 3.1 | 像素风硬性约束——你写的 CSS 面板必须遵守 |
| **第四章全章** | EventBus 所有事件——你监听和发送的完整合同 |
| **第五章全章** | FastAPI 接口契约——你实现的 API 必须与此完全对应 |
| 第六章全章 | 目录结构——你的文件放哪里，`api/` 和 `frontend/panels/` 的边界 |

**必读代码**（动手前先读，否则可能改错地方）：

| 文件 | 读什么 |
|------|-------|
| `cyber_planner.py` 前 100 行 | `KG_PATH` 常量、`CyberBrainStore.__init__` 参数、整体结构 |
| `cyber_planner.py` 的 `handle_review()` | 理解现有 CLI 交互流程，再决定怎么解耦 |
| `cyber_planner.py` 的 `run()` 方法 | 理解 REPL 主循环，提取 `process_message()` 的边界 |
| `pipelines/decision_log.py` | 路径硬编码现状（33–37 行），所有公开函数的入参和返回值 |

**相关简报**：
- `docs/AGENT2_DESIGN_BRIEF.md` 第五节任务清单——了解 UI 设计稿的交付顺序，判断哪些面板可以先开工

可以暂时不读的：第二章（游戏空间结构）、第三章（资产规范）——那是 Agent 2/3 的事。

---

## 三、依赖与启动条件

Agent 4 的工作分两条轨道，启动条件不同：

### 后端轨道：现在立即可以开始

后端工作不依赖任何其他 Agent，TECH_SPEC 已经定义了所有接口契约。

```
立即可以开始 ──────────────────────────────────────────────────────
  ↓
B1：decision_log.py 路径参数化
  ↓
B2–B5：handle_* 函数 I/O 解耦（四个函数，可并行）
  ↓（以上完成后）
B6：FastAPI app 骨架 + 健康检查
  ↓
B7–B11：五组路由（可并行）
  ↓
后端完成，前端面板接入真实 API
```

**关键约束**：B2–B5 的 I/O 解耦必须在 B7–B11 路由之前完成。路由层只调用已解耦的函数，不允许在 FastAPI handler 里直接写 `input()` 或 `print()`。

---

### 前端轨道：现在也可以开始，用 mock 数据

前端面板开发不需要等后端路由完成，也不需要等 Agent 3 的游戏场景。用以下策略并行推进：

**用 mock 数据开发**：`client.js` 提供一个 `USE_MOCK` 开关，`true` 时返回本地硬编码数据，`false` 时调用真实 API。面板开发期间全程用 mock，后端完成后切换开关验证。

**用手动 `dispatchEvent` 测试 EventBus**：不需要等 Agent 3 完成游戏场景，直接在浏览器控制台手动触发事件测试面板打开/关闭行为。

```
立即可以开始 ──────────────────────────────────────────────────────
  ↓
F1：index.html 骨架 + style/tokens.css
  ↓
F2：client.js（含 USE_MOCK 开关）
  ↓
F3–F9：面板和 HUD（大部分可并行，见下表）
```

**各面板启动条件细化**：

| 面板 | 可以开始的条件 | 等待内容（如有） |
|------|--------------|----------------|
| F3 对话框 | 立即（mock SSE） | Agent 2 的对话框设计稿（有稿后调整样式） |
| F4 任务板面板 | 立即（mock 数据） | Agent 2 的任务板设计稿 |
| F5 /review 审批面板 | 立即（mock 数据） | Agent 2 的审批面板设计稿 |
| F6 /kg 面板 | 立即（mock 数据） | Agent 2 的 /kg 设计稿 |
| F7 /prune 面板 | 立即（mock 数据） | Agent 2 的 /prune 设计稿 |
| F8 房间入口确认提示 | 立即（不需要设计稿） | — |
| F9 HUD 顶部栏 | 立即（不需要设计稿） | — |
| F10 EventBus 全量接入 | F3–F9 骨架完成后 | — |

---

### 两条轨道的汇合点

后端和前端轨道各自推进，在以下节点汇合：

```
后端轨道                    前端轨道
────────                    ────────
B1–B5 I/O 解耦              F1–F9 面板开发（mock 数据）
      ↓                            ↓
B6–B11 FastAPI 路由         F10 EventBus 全量接入
      └──────────┬──────────────────┘
                 ↓
          关闭 USE_MOCK，接入真实 API
                 ↓
          端到端联调（对话 streaming、审批写 KG、通知角标）
                 ↓
          部署，对外提供 URL
```

---

## 四、任务清单

### ── 后端轨道 ──

---

#### B1：`decision_log.py` 路径参数化
**产出**：修改后的 `pipelines/decision_log.py`  
**改动内容**：将模块顶层的硬编码路径常量（第 33–37 行）改为可通过函数参数传入，同时保留默认值维持向后兼容。  
**验收标准**：
- 所有读写函数（`write_pending`、`read_awaiting`、`resolve_approval` 等）接受可选的 `logs_dir: Path = LOGS_DIR` 参数
- 现有的 CLI 调用方式不变（不传参数时行为与之前完全一致）
- 现有测试全部通过

---

#### B2：`handle_review()` I/O 解耦
**产出**：`cyber_planner.py` 中新增两个纯函数，原 `handle_review()` 改为调用这两个函数  
**改动内容**：

```python
# 新增：返回数据，不做任何 I/O
def get_review_items() -> list[dict]:
    """返回所有 status='awaiting' 的条目"""

def process_review_decision(
    item_id: str,
    decision: str,           # "approved_kg" / "approved_log" / "rejected"
    user_note: str = "",
    importance: int | None = None,
    description: str | None = None,
) -> dict:
    """执行审批决策，返回 {"success": bool, "item_id": str}"""

# 原 handle_review() 保留，改为调用上面两个函数 + 自己处理 input()/print()
```

**验收标准**：
- `get_review_items()` 和 `process_review_decision()` 内部无任何 `input()` / `print()` 调用
- 原 `handle_review()` CLI 行为不变
- `approved_kg` 时正确调用 `CyberBrainStore.create_node()`

---

#### B3：`handle_kg()` I/O 解耦
**产出**：新增纯函数，原 `handle_kg()` 改为调用它们  

```python
def get_kg_nodes(layer: str | None = None, include_archived: bool = False) -> list[dict]:
    """返回节点列表，可按 layer 过滤"""

def get_kg_node(node_id: str) -> dict | None:
    """返回单个节点完整详情"""

def get_kg_graph() -> dict:
    """返回 {"nodes": [...], "links": []} 力导向图数据"""
```

**验收标准**：三个函数内部无 `input()` / `print()`，原 CLI 行为不变。

---

#### B4：`handle_prune()` I/O 解耦
**产出**：新增纯函数，原 `handle_prune()` 改为调用它们  

```python
def get_prune_candidates() -> dict:
    """返回 {"stats": {"critical": N, "warning": N, "healthy": N}, "candidates": [...]}"""
    # staleness = days_since_last_access / importance
    # critical: staleness > 阈值高; warning: staleness > 阈值低; healthy: 其余

def archive_node(node_id: str, reason: str = "") -> dict:
    """归档节点，返回 {"success": bool}"""

def boost_node_importance(node_id: str, new_importance: int) -> dict:
    """更新 importance，返回 {"success": bool, "new_importance": int}"""
```

**验收标准**：三个函数内部无 `input()` / `print()`，原 CLI 行为不变。

---

#### B5：对话核心 `process_message()` 提取
**产出**：从 `run()` REPL 提取独立的异步生成器函数  

```python
async def process_message(user_input: str) -> AsyncGenerator[str, None]:
    """
    处理一条用户消息，流式 yield token 字符串。
    对话历史维护在 CyberBrainStore 实例的内存中（单用户 MVP）。
    反刍判断逻辑不变，反刍触发时额外 yield 一个特殊标记 token。
    """
```

**验收标准**：
- 函数内部无 `input()` / `print()`
- 流式输出：每次 Claude API 返回 token 时立即 yield，不等全部完成
- 反刍触发时 yield `"[REFLECTION_TRIGGERED]"` 标记（FastAPI 层识别并转为 SSE reflection 事件）
- 原 `run()` REPL 改为调用 `process_message()` 并自己处理打印，行为不变
- FastAPI 路由层负责识别流中的 `"[REFLECTION_TRIGGERED]"` 标记，将其转换为 SSE `{"type": "reflection", "triggered": true}` 事件发送给前端，该标记本身不作为 `token` 类型发送

---

#### B6：FastAPI 应用骨架
**产出**：`api/main.py`、`api/schemas.py`  
**验收标准**：
- `uvicorn api.main:app --reload --port 8000` 可正常启动
- `GET /api/health` 返回 `{"status": "ok"}`
- CORS 允许 `http://localhost:3000`
- `api/schemas.py` 包含 TECH_SPEC 第五章 5.7 定义的全部四个 Pydantic 模型（`KGNode`、`ReviewItem`、`Notification`、`PruneCandidate`）

---

#### B7：`/api/chat` 路由（SSE 流式输出）
**产出**：`api/routes/chat.py`  
**验收标准**：
- `POST /api/chat` 调用 `process_message()`，以 SSE 格式流式返回
- SSE 格式严格遵守 TECH_SPEC 第五章 5.2 的三种 type（`token` / `done` / `reflection`）
- `DELETE /api/chat/history` 清空对话历史，返回 `{"cleared": true}`
- 用 `curl` 或 Postman 可验证 token 逐字流式到达

---

#### B8：`/api/review/*` 路由
**产出**：`api/routes/review.py`  
**验收标准**：
- `GET /api/review/items` 调用 `get_review_items()`，返回格式符合 5.3
- `GET /api/review/count` 返回 `{"count": N}`
- `POST /api/review/items/{item_id}/decide` 调用 `process_review_decision()`，参数验证完整
- `approved_kg` 决策后 KG 文件中确实新增了对应节点

---

#### B9：`/api/kg/*` 路由
**产出**：`api/routes/kg.py`  
**验收标准**：
- `GET /api/kg/nodes` 支持 `layer` 和 `includeArchived` query 参数
- `GET /api/kg/nodes/{node_id}` 节点不存在时返回 404
- `GET /api/kg/graph` 返回 `{"nodes": [...], "links": []}` ，`links` 为空数组（Phase 1）

---

#### B10：`/api/prune/*` 路由
**产出**：`api/routes/prune.py`  
**验收标准**：
- `GET /api/prune/candidates` 返回分组数据，`stalenessScore` 有实际计算值
- `POST /api/prune/{node_id}/archive` 归档后节点 `archived: true`
- `POST /api/prune/{node_id}/boost` importance 更新后可通过 `/api/kg/nodes/{node_id}` 验证

---

#### B11：`/api/notifications/*` 路由
**产出**：`api/routes/notifications.py`  
**验收标准**：
- `GET /api/notifications` 只返回 `consumed: false` 的条目
- `POST /api/notifications/{id}/consume` 后该条目不再出现在列表中

---

### ── 前端轨道 ──

---

#### F1：`index.html` 骨架 + `style/tokens.css`
**产出**：`frontend/index.html`、`frontend/style/tokens.css`  
**验收标准**：
- `index.html` 加载 Phaser.js CDN、`game/main.js`、所有面板 JS 文件
- `tokens.css` 包含 TECH_SPEC 第一章 1.5 的全部 7 个 CSS 变量
- 页面背景色为 `var(--color-bg)`（`#0d1117`），无白色闪烁

---

#### F2：`client.js`（API 请求封装 + mock 开关）
**产出**：`frontend/client.js`  
**验收标准**：
- 顶部有 `const USE_MOCK = true` 开关
- `USE_MOCK = true` 时所有函数返回本地硬编码数据，不发任何网络请求
- `USE_MOCK = false` 时所有函数调用对应的 `/api/*` 端点
- 覆盖 TECH_SPEC 第五章全部路由：`chat()`、`getReviewItems()`、`decideReviewItem()`、`getKgNodes()`、`getKgGraph()`、`getPruneCandidates()`、`archiveNode()`、`boostNode()`、`getNotifications()`、`consumeNotification()`
- SSE 对话：`chatStream(message, onToken, onDone, onReflection)` 回调式接口

---

#### F3：对话框面板
**产出**：`frontend/panels/dialogue.js` + `frontend/style/panels.css`（对话框部分）  
**验收标准**：
- 监听 `cyber:npc:interact`，打开对话框，发送 `cyber:panel:opened { panelId: "dialogue" }`
- 调用 `client.chatStream()`，token 逐字追加到文字区
- streaming 时显示 `|` 光标（8fps 闪烁），完成后光标消失
- `reflection` 触发时右上角显示「💡 正在更新认知图谱…」，3 秒后消失
- 点击 X 或按 Esc 关闭，发送 `cyber:panel:closed { panelId: "dialogue" }`
- NPC 头像取 `npcId` 对应 Sprite Sheet 的 idle 行第 0 帧（占位阶段用颜色方块）
- 若触发来源是 `cyber:object:interact`（有 `contextHint` 字段），打开对话框时将 `contextHint` 作为本轮对话的系统提示前缀，连同用户消息一起传给 `client.chatStream()`

---

#### F4：任务板面板（/review 入口）
**产出**：`frontend/panels/taskboard.js`  
**验收标准**：
- 监听 `cyber:object:interact` 且 `objectId === "taskboard"`，打开面板
- 调用 `client.getReviewItems()` 展示待审批条目列表
- 注意区分触发来源：`objectId === "taskboard"` 时直接打开任务板；`objectId` 为 GymScene 物件时应打开对话框（由 F3 处理），F4 不响应这类事件
- 每条展示来源标签（按 TECH_SPEC 5.3 的 sourceMode 映射表）+ 内容摘要
- 空状态展示提示文案
- 点击某条目跳转打开 F5（/review 审批面板）

---

#### F5：/review 审批面板
**产出**：`frontend/panels/review.js`  
**验收标准**：
- 实现 TECH_SPEC 2.4 定义的四种状态（LOG 路由 / KG 路由有相似节点 / 无相似节点 / 空状态）
- importance 滑块 1–10，像素风样式
- 支持键盘快捷键 Y / N / s / q
- 提交决策调用 `client.decideReviewItem()`
- 全部处理完毕时发送 `cyber:review:done { processedCount: N }`

---

#### F6：/kg 知识图谱面板（卡片视图）
**产出**：`frontend/panels/kg.js`  
**验收标准**：
- 三列布局（Id / Ego / Superego），Tab 激活态用对应层级色
- 节点卡片显示 importance 色标（1–3 灰、4–6 白、7–8 黄、9–10 红）+ 标题 + 描述预览
- 归档节点灰度处理，默认隐藏，「显示已归档」开关控制
- 点击节点展开完整 evidence 列表

---

#### F7：/prune 老化管理面板
**产出**：`frontend/panels/prune.js`  
**验收标准**：
- 顶部展示三类统计卡片（候选归档 / 接近阈值 / 健康）
- 逐条展示候选节点 + staleness 分数 + 三个操作按钮（归档 / 提升 importance / 跳过）
- 操作后列表实时更新（移除已处理条目）
- 全部处理完毕展示总结提示

---

#### F8：房间入口确认提示
**产出**：`frontend/panels/dialogue.js` 中的 room-entry 逻辑（或独立文件）  
**验收标准**：
- 监听 `cyber:door:approach`，显示浮窗（约 320×120px，居中偏上）
- 显示 `roomName` + `modeDescription` + Y/N 按钮
- 按 Y：发送 `cyber:door:confirmed { targetScene }` + `cyber:panel:closed { panelId: "room-entry" }`
- 按 N 或 Esc：发送 `cyber:door:cancelled` + `cyber:panel:closed { panelId: "room-entry" }`

---

#### F9：HUD 顶部栏
**产出**：`frontend/style/hud.css` + `index.html` 中的 HUD HTML  
**验收标准**：
- `position: fixed`，顶部薄条，不遮挡游戏主体
- 监听 `cyber:scene:changed`，更新当前房间名显示
- 监听 `cyber:notification:badge`，`count > 0` 时显示通知角标数字

---

#### F10：EventBus 全量接入与联调
**产出**：所有面板的 EventBus 监听完整、与 Agent 3 的事件名精确对齐  
**验收标准**：
- 关闭 `USE_MOCK`，所有面板调用真实 API 数据正常展示
- 与 Agent 3 的 Phaser 场景联调：走近 NPC 按 E → 对话框打开 → 角色停止移动 → 关闭对话框 → 角色恢复移动
- 走近健身房门洞 → 确认提示弹出 → 按 Y → 场景切换到 GymScene
- 任务板审批完成 → Phaser 中任务板物件角标消失

---

## 五、不在范围内

| 不做的事 | 原因 |
|---------|------|
| 修改 `cyber_planner.py` 的 KG 操作逻辑、反刍判断、prompt 构造 | 核心业务逻辑已稳定且有测试，只动 I/O 层 |
| 实现用户注册、登录、session、JWT | MVP 单用户 Mode A，不需要 auth |
| 实现多用户 KG 隔离 | Phase 2+ 内容，现在不做 |
| 写任何 Phaser 场景或游戏逻辑 | Agent 3 负责 |
| 修改或生成任何美术资产 | Agent 2 负责 |
| 实现 /kg 力导向图视图 | P2 内容，卡片视图优先；力导向图等设计稿到位后再做 |
| 为 Phase 2 专项房间（办公室/学习室）实现后端专项模式 | Phase 2 内容 |
| 自行新增 API 路由或 EventBus 事件名 | 必须先走上报机制，由 Agent 1 更新 TECH_SPEC |

---

## 六、上报机制

工作中遇到以下情况时，**不要自行假设，填写上报模板提交给 Agent 1 判断**：

- `cyber_planner.py` 的某个函数解耦方式不确定，担心改动影响现有逻辑
- TECH_SPEC 第五章的接口 schema 与实际后端数据结构有出入
- EventBus 事件的 payload 字段不够用，需要新增
- Agent 3 的实际事件名或 payload 与 TECH_SPEC 第四章不一致
- `USE_MOCK` 模式下发现业务逻辑问题，需要澄清需求

**上报方式**：在 `docs/OPEN_QUESTIONS.md` 末尾追加，使用以下模板：

```
## Q{编号} [Agent 4] [{日期}]
**问题**：
**背景**：
**我的猜测**：
**影响范围**：
**紧急程度**：高 / 中 / 低
**状态**：⏳ 待解答
```

**两条轨道遇到阻塞时的处理原则**：
- 后端某个函数解耦有疑问 → 先跳过该路由，继续做其他路由，上报问题等待解答
- 前端面板样式未收到设计稿 → 用骨架样式先实现交互逻辑，样式等稿到位后补
- EventBus 与 Agent 3 对不上 → 先用 `console.log` 记录收到的事件，上报给 Agent 1 仲裁，不要单方面修改事件名

---

