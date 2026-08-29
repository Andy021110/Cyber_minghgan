# WorkBuddy 启动 Prompt 合集

> 每次开发时：打开 WorkBuddy → 新建任务 → 粘贴对应 Prompt → 附上指定文件 → 提交  
> 建议使用「软件开发团队」专家团，或拆分为独立专家任务。

---

## 使用方式

1. 打开 WorkBuddy，点击「新建任务」
2. 从下方选择对应的任务 Prompt，**完整复制粘贴**到任务描述框
3. 在附件区上传指定的文件（每个 Prompt 下方有「附件清单」）
4. 提交，等 PM 角色读取完后确认任务分解再继续

---

## ⚠️ 重要说明

WorkBuddy 生成的代码在对话窗口中，**需要你手动复制到本地对应路径**。  
项目根目录：`/Users/minghan/Desktop/知识蒸馏/元宝-明翰/`

**关于记忆**：WorkBuddy 每个任务是独立的，不保留上次任务的对话记忆。  
解决方式：每次新建任务时，把上次已完成的文件路径列表加到 Prompt 开头的「当前进度」里：

```
## 当前进度（续跑时填写，首次可删除此节）
已完成的文件：
- frontend/game/main.js
- frontend/game/roomConfig.js
- frontend/game/colors.js
从 G3（WorldScene.js）开始继续。
```

**关于步进节奏**：每个 Prompt 末尾已包含「步进执行」规则，工程师每次只输出一个文件，  
你确认后说「继续」推进下一步，不会一次性输出几百行代码。

---

---

## 任务一：Phaser.js 游戏层开发

### Prompt

```
## 项目背景

「赛博明翰」是一个像素风 RPG × 认知镜子 Web App。玩家在一栋像素房子里行走，进入不同房间触发不同的 AI 管家对话。

技术架构：
- 游戏世界层：Phaser.js 3（Canvas，像素风渲染）
- 功能面板层：原生 HTML/CSS/JS（叠加在 Canvas 上，z-index 更高）
- 两层通信：window.dispatchEvent 自定义事件（EventBus）
- 后端：FastAPI（另一个任务负责，本任务只做游戏层）

## 本次任务

开发 Phaser.js 游戏层，实现所有游戏场景、角色移动、NPC 交互、触发区检测和 EventBus 通信。

**所有技术规格已在附件 `game_context.md` 中定义，请工程师在开始前完整阅读。**

## 开发顺序（按此顺序实现，不可乱序）

1. **G1 项目结构**：`frontend/game/main.js` + `frontend/game/roomConfig.js`
   - roomConfig.js 必须包含全部四个场景（WorldScene/GymScene/OfficeScene/StudyScene）
   - main.js 必须从 roomConfig.js 数组动态注册场景，不能硬编码场景类
   - Phaser config 必须包含 `pixelArt: true`, `width: 720`, `height: 450`, `zoom: 2`

2. **G2 颜色常量**：`frontend/game/colors.js`
   - 使用 0xRRGGBB 格式，不能用 CSS 变量（Canvas 里无效）
   - 必须包含附件中定义的全部 7 个颜色

3. **G3 WorldScene 骨架**：`frontend/game/scenes/WorldScene.js`
   - 用纯色矩形代替 Tilemap（占位）
   - 加载完成后发送 `cyber:scene:changed { sceneKey: 'WorldScene', roomName: '中央区' }`

4. **G4 玩家移动**：`frontend/game/objects/Player.js`
   - WASD/方向键四方向移动
   - 提供 `enableInput()` / `disableInput()` 方法
   - 碰撞检测用矩形碰撞体

5. **G5 触发区系统**：WorldScene 和 GymScene 中的触发逻辑
   - PROXIMITY（走入自动触发）和 INTERACT（走入后按 E）两种类型
   - 按附件事件清单发送对应 EventBus 事件

6. **G6 EventBus 接收侧**
   - 监听 `cyber:panel:opened` → 调用 `player.disableInput()`
   - 监听 `cyber:panel:closed` → 调用 `player.enableInput()`
   - 监听 `cyber:door:confirmed` → 淡出 → `scene.start(targetScene)`

7. **G7 场景切换动画**：淡出 300ms → scene.start → 淡入 300ms

8. **G8 NPC 通用类**：`frontend/game/objects/NPC.js`
   - 接收 npcId、spriteKey、坐标
   - 玩家按 E 发送 `cyber:npc:interact { npcId, npcName }`

9. **G9 GymScene**：`frontend/game/scenes/GymScene.js`
   - 健康管家 NPC（使用 NPC 通用类）
   - 体重日历和训练记录本的 INTERACT 触发区（附件中有 objectId 和 contextHint 值）
   - 出口区走入直接返回 WorldScene（无需确认）

10. **G10 Phase 2 Stub 场景**：`OfficeScene.js`、`StudyScene.js`
    - 最小实现：显示「建设中」文字 + 返回 WorldScene 的出口触发区

11. **G11 通知角标查询**：WorldScene 加载完成时查询 `GET /api/notifications`，根据数量发送 `cyber:notification:badge { count }`

## 硬性约束

- 所有文件写入 `frontend/game/` 目录
- 现阶段全部用占位资产（纯色矩形代替地图，几何形状代替角色）
- 不写任何 HTML 面板、CSS 样式文件、FastAPI 接口
- 事件名、objectId、npcId 等常量必须与附件定义完全一致，不得自行命名
- Phase 2 门洞（office/study）的 PROXIMITY 触发显示「即将开放」提示，不发送 `cyber:door:approach`

## 遇到附件未覆盖的问题

在回复中用以下格式标注：
【Q：问题描述 | 背景：在哪个任务遇到 | 我的猜测：如果必须选我会怎么做】
然后继续做不受影响的任务，不要因为一个问题停工。

## 步进执行规则（PM 传达工程师遵守）

每次只实现一个文件或一个函数：
1. 先声明「准备实现：G[N] xxx」
2. 输出代码，单次不超过 80 行
3. 输出完成后说「G[N] 完成，等待确认后继续」
4. 等待用户回复「继续」后再进行下一步

## 输出格式

每个文件单独输出，格式：
```
// 文件路径：frontend/game/xxx/FileName.js
[代码内容]
```
```

## 本地验证（每批文件保存后运行）

```bash
# 把工程师输出的代码按「文件路径」注释保存到本地后
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
python -m http.server 3000 --directory frontend
# 浏览器打开 http://localhost:3000，观察 Canvas 是否正常渲染
```

```javascript
// 浏览器控制台测试 EventBus（不需要后端）
window.dispatchEvent(new CustomEvent('cyber:npc:interact', {
  detail: { npcId: 'cyber_minghan', npcName: '赛博明翰' }
}));
```

### 附件清单（任务一）

| 文件 | 说明 |
|------|------|
| `docs/context/game_context.md` | 完整技术规格：Phaser 配置、场景常量、EventBus 事件清单 |
| `docs/AGENT3_GAME_BRIEF.md` | 任务清单、验收标准、角色边界 |

---

---

## 任务二：FastAPI 后端开发

### Prompt

```
## 项目背景

「赛博明翰」Web App 的后端，基于 Python 现有代码包一层 FastAPI，提供 REST 接口供前端调用。

现有代码结构：
- `cyber_planner.py`：核心业务逻辑（CyberBrainStore 类 + handle_review/kg/prune + run()）
- `pipelines/decision_log.py`：日志读写（路径硬编码，需参数化）
- **不允许修改业务逻辑**（KG 操作、反刍判断、prompt 构造），只做 I/O 层解耦

## 本次任务

分两阶段，第一阶段必须全部完成后才能进入第二阶段。

### 第一阶段：I/O 解耦（必须先完成）

原因：现有函数直接调用 input()/print()，无法被 FastAPI handler 调用。
解耦原则：提取纯函数（无 input/print），原 CLI 函数改为调用纯函数。

**B1：decision_log.py 路径参数化**
- 将 `pipelines/decision_log.py` 第 33–37 行的路径常量改为所有读写函数的可选参数 `logs_dir: Path = LOGS_DIR`
- 向后兼容：不传参数时行为与之前完全一致

**B2：handle_review() I/O 解耦**
在 `cyber_planner.py` 中新增：
```python
def get_review_items() -> list[dict]: ...
def process_review_decision(item_id, decision, user_note="", importance=None, description=None) -> dict: ...
```

**B3：handle_kg() I/O 解耦**
```python
def get_kg_nodes(layer=None, include_archived=False) -> list[dict]: ...
def get_kg_node(node_id: str) -> dict | None: ...
def get_kg_graph() -> dict: ...
```

**B4：handle_prune() I/O 解耦**
```python
def get_prune_candidates() -> dict: ...
def archive_node(node_id, reason="") -> dict: ...
def boost_node_importance(node_id, new_importance) -> dict: ...
```

**B5：process_message() 提取**
```python
async def process_message(user_input: str) -> AsyncGenerator[str, None]:
    # 流式 yield token 字符串
    # 反刍触发时 yield "[REFLECTION_TRIGGERED]"（FastAPI 路由层识别并转为 SSE reflection 事件）
```

### 第二阶段：FastAPI 路由（I/O 解耦完成后）

**B6：FastAPI 骨架**
- `api/main.py`：app 实例、CORS（允许 localhost）、挂载路由
- `api/schemas.py`：KGNode / ReviewItem / Notification / PruneCandidate 四个 Pydantic 模型
- `GET /api/health` 返回 `{"status": "ok"}`

**B7：/api/chat 路由**（`api/routes/chat.py`）
- `POST /api/chat`：SSE 流式输出，三种 type：token / done / reflection
- `DELETE /api/chat/history`：清空历史

**B8–B11：其余路由**（各一个文件）
- B8：`api/routes/review.py`（GET items、GET count、POST decide）
- B9：`api/routes/kg.py`（GET nodes、GET nodes/{id}、GET graph）
- B10：`api/routes/prune.py`（GET candidates、POST archive、POST boost）
- B11：`api/routes/notifications.py`（GET list、POST consume）

所有接口的完整规格（路由、请求体、响应体、Schema）在附件 `api_context.md` 中。

## 硬性约束

- 不修改 CyberBrainStore 的 KG 操作逻辑、反刍判断、prompt 构造
- FastAPI handler 里严禁出现 input() 或 print()
- SSE 事件格式严格按照附件中的定义（token/done/reflection 三种 type）
- 不实现用户注册、登录、session、JWT（单用户 MVP，不需要 auth）

## 遇到附件未覆盖的问题

在回复中标注：
【Q：问题 | 背景：在哪个任务 | 我的猜测：...】
然后跳过当前任务，继续其他任务。

## 步进执行规则（PM 传达工程师遵守）

每次只实现一个函数或一个文件：
1. 先声明「准备实现：B[N] xxx」
2. 输出代码，单次不超过 80 行
3. 写完后说「B[N] 完成，等待确认后继续」
4. 等待用户回复「继续」后再进行下一步

## 输出格式

每个修改文件单独输出，格式：
```
# 文件路径：api/routes/chat.py  （或 pipelines/decision_log.py 等）
[代码内容]
```
如果是修改现有文件，只输出有改动的函数，并注明「在 xxx 函数之后插入」。
```

## 本地验证（B6 完成后）

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
uvicorn api.main:app --reload --port 8000
curl http://localhost:8000/api/health  # 应返回 {"status":"ok"}
curl http://localhost:8000/api/review/items  # 应返回 [] 或列表
```

### 附件清单（任务二）

| 文件 | 说明 |
|------|------|
| `docs/context/api_context.md` | 完整 API 接口契约、Schema 定义、I/O 解耦函数签名 |
| `docs/AGENT4_PANEL_BRIEF.md` | 后端任务详细说明、验收标准 |
| `docs/context/cyber_planner_excerpt.md` | cyber_planner.py 关键摘录（原文件 1556 行，含改动所需的全部接口和数据结构） |
| `pipelines/decision_log.py` | 需要参数化的日志模块 |

---

---

## 任务三：HTML 前端面板开发

### Prompt

```
## 项目背景

「赛博明翰」Web App 的前端功能面板层。HTML/CSS/JS 面板叠加在 Phaser.js Canvas 上方（z-index 更高），通过 window.dispatchEvent 自定义事件（EventBus）与游戏层通信，通过 fetch 调用 FastAPI 后端。

## 本次任务

开发所有 HTML/CSS/JS 功能面板和 HUD，先用 mock 数据开发，后端完成后切换开关对接真实 API。

### F1：index.html + tokens.css

`frontend/index.html`：
- 加载 Phaser.js CDN（https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js）
- 必须包含 `<div id="game-container"></div>`（Phaser 游戏层挂载点，位置在面板层之前）
- 加载 `game/main.js`（type="module"）
- 加载 `client.js` 和所有面板 JS
- HUD HTML 结构（见附件 panel_context.md）
- 背景色 `var(--color-bg)`，无白色闪烁

`frontend/style/tokens.css`：包含附件中定义的全部 7 个 CSS 变量

### F2：client.js

`frontend/client.js`：
- 顶部 `const USE_MOCK = true;` 开关
- `USE_MOCK = true` 时所有函数返回硬编码数据，不发任何网络请求
- `USE_MOCK = false` 时调用对应 `/api/*` 端点
- 覆盖全部 11 个函数（见附件 panel_context.md 的 client.js 结构部分）
- SSE 对话：`chatStream(message, onToken, onDone, onReflection)` 回调式接口

### F3：对话框面板

`frontend/panels/dialogue.js` + `frontend/style/panels.css`（对话框部分）：
- 监听 `cyber:npc:interact` → 打开，发送 `cyber:panel:opened { panelId: "dialogue" }`
- 监听 `cyber:object:interact`（objectId 不是 "taskboard"）→ 携带 contextHint 打开
- 调用 `client.chatStream()`，token 逐字追加
- streaming 时显示 `|` 光标（steps() 8fps 闪烁），完成后消失
- reflection 触发时右上角显示「💡 正在更新认知图谱…」3 秒后消失
- 点击 X 或按 Esc 关闭，发送 `cyber:panel:closed { panelId: "dialogue" }`

房间入口确认提示（可在 dialogue.js 内或独立文件）：
- 监听 `cyber:door:approach { targetScene, roomName, modeDescription }`
- 约 320×120px 浮窗，居中偏上
- 按 Y → 发送 `cyber:door:confirmed { targetScene }` + `cyber:panel:closed { panelId: "room-entry" }`
- 按 N/Esc → 发送 `cyber:door:cancelled` + `cyber:panel:closed { panelId: "room-entry" }`

### F4：任务板面板

`frontend/panels/taskboard.js`：
- 只监听 `cyber:object:interact` 且 `objectId === "taskboard"`（不响应 GymScene 物件）
- 调用 `getReviewItems()`，按 sourceMode 展示来源标签
- 空状态展示提示文案
- 点击条目打开 review 面板

### F5：/review 审批面板

`frontend/panels/review.js`：
- 四种状态：LOG 路由 / KG 路由有相似节点 / 无相似节点 / 空状态
- importance 滑块 1–10，像素风样式
- 键盘快捷键：Y/N/s/q
- 全部处理完发送 `cyber:review:done { processedCount: N }`

### F6：/kg 知识图谱面板

`frontend/panels/kg.js`：
- 三列布局（Id/Ego/Superego），Tab 用对应层级色
- importance 色标：1–3 灰、4–6 白、7–8 黄、9–10 红
- 「显示已归档」开关
- 点击节点展开 evidence 列表

### F7：/prune 老化管理面板

`frontend/panels/prune.js`：
- 顶部三类统计卡片
- 逐条展示 + 三个操作按钮（归档/提升/跳过）
- 操作后实时移除已处理条目

### F9：HUD 顶部栏

`frontend/style/hud.css` + index.html 中的 HUD HTML：
- `position: fixed`，顶部薄条
- 监听 `cyber:scene:changed` 更新房间名
- 监听 `cyber:notification:badge` 更新角标数字

## 硬性约束

- 所有颜色使用 CSS 变量（如 `var(--color-bg)`），不硬编码色值
- 严格遵守像素风 CSS 约束（见附件）
- 不写任何 Phaser 场景或游戏逻辑代码
- F3 的对话框打开时，contextHint 作为系统消息前缀（不直接显示给用户）
- F4 只响应 objectId === "taskboard"，GymScene 的物件（weight_calendar/training_log）由 F3 处理

## 遇到附件未覆盖的问题

标注：【Q：问题 | 背景：... | 我的猜测：...】，然后继续其他任务。

## 步进执行规则（PM 传达工程师遵守）

每次只实现一个文件或一个函数：
1. 先声明「准备实现：F[N] xxx」
2. 输出代码，单次不超过 80 行
3. 输出完成后说「F[N] 完成，等待确认后继续」
4. 等待用户回复「继续」后再进行下一步

## 输出格式

每个文件单独输出：
```
// 文件路径：frontend/panels/dialogue.js
[代码内容]
```
```

## 本地验证（F1 完成后）

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
python -m http.server 3000 --directory frontend
# 浏览器打开 http://localhost:3000
# 预期：页面加载不报错，Canvas 区域可见，HUD 顶部栏显示
```

### 附件清单（任务三）

| 文件 | 说明 |
|------|------|
| `docs/context/panel_context.md` | 完整面板规格：EventBus 事件、CSS 变量、client.js 结构、各面板行为 |
| `docs/context/api_context.md` | API 数据结构定义（ReviewItem / KGNode / PruneCandidate 字段），**写 mock 数据时必须参考** |
| `docs/AGENT4_PANEL_BRIEF.md` | 前端任务详细说明、验收标准 |

---

---

## 你（架构师）的日常操作

### 处理 WorkBuddy 输出的问题标注

WorkBuddy 生成的回复里如果有 `【Q：...】` 标注，把它整理到 `docs/OPEN_QUESTIONS.md`：

```markdown
## Q[编号] [任务来源] [日期]
**问题**：[从 Q 标注复制]
**背景**：[从背景字段复制]
**我的猜测**：[从猜测字段复制]
**影响范围**：[评估]
**紧急程度**：高 / 中 / 低
**状态**：⏳ 待解答
```

解答后，在新建任务时把解答结论加到 Prompt 开头的「补充约束」中：

```
## 补充约束（前序任务已解答的问题）
- Q1 已解答：xxx 的处理方式是 yyy
```

### 把代码保存到本地

WorkBuddy 每次输出代码后，对照「文件路径」注释，把代码复制到本地对应路径。  
建议按顺序保存，每保存一批先在本地运行验证再继续。

### 验证命令

```bash
# 后端验证（B6 完成后）
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
uvicorn api.main:app --reload --port 8000
curl http://localhost:8000/api/health

# 前端验证（F1 完成后）
python -m http.server 3000 --directory frontend
# 浏览器打开 http://localhost:3000
```
