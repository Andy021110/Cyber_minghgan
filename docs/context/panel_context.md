# 前端面板开发上下文（供 Agent 4 前端 / WorkBuddy 面板任务使用）

> 本文件摘录自 TECH_SPEC.md，覆盖 HTML/CSS/JS 功能面板开发所需的全部规格。

---

## 架构定位

```
┌──────────────────────────────────┐
│   HTML/CSS 功能面板层（z-index 高）│  ← 你负责这一层
│   对话框 / /review / /kg / /prune │
└──────────────────────────────────┘
┌──────────────────────────────────┐
│   Phaser.js canvas 层             │  ← Agent 3 负责
│   游戏世界、角色、NPC、场景        │
└──────────────────────────────────┘
```

面板以 `position: fixed` 叠加在 Phaser canvas 上方。两层只通过 EventBus（`window.dispatchEvent`）通信，不直接调用对方的函数。

### index.html 结构要求

Phaser canvas 挂载到 `<div id="game-container"></div>`，面板层叠在其上：

```html
<body>
  <div id="game-container"></div>  <!-- Phaser canvas 挂载点，必须有此 id -->
  <div id="hud">...</div>          <!-- HUD 顶部栏 -->
  <!-- 面板层 HTML 结构 -->
</body>
```

`game-container` 的 div 必须在所有面板之前出现，否则 Phaser 初始化失败。

---

## 色彩 CSS 变量（必须使用，不得硬编码色值）

```css
:root {
  --color-bg:          #0d1117;  /* 游戏世界底色 */
  --color-card-bg:     #161b22;  /* 功能面板底色 */
  --color-border:      #30363d;  /* 边框 / 分割线 */
  --color-text:        #c9d1d9;  /* 正文主色 */
  --color-id:          #e05c5c;  /* Id 层 / 危险 */
  --color-ego:         #3fb950;  /* Ego 层 / 成功 */
  --color-superego:    #f0a500;  /* Superego 层 / 提示 */
}
```

---

## 像素风 CSS 约束

| 属性 | 规范 |
|------|------|
| 圆角 | 0px（最多 2px） |
| 阴影 | `drop-shadow(2px 2px 0px #000)`，模糊 0px |
| 动画 | `steps()` 帧动画，8fps |
| 字体（标题） | `'Press Start 2P', monospace`（英文标题专用） |
| 字体（内容） | `'Noto Sans Mono', monospace`（中英文内容） |

---

## client.js 结构要求

```javascript
// frontend/client.js
const USE_MOCK = true;  // true = 本地 mock 数据；false = 调用真实 API

// USE_MOCK = true 时所有函数返回硬编码数据，不发网络请求
// USE_MOCK = false 时调用 /api/* 端点

// 必须覆盖的函数：
export async function chatStream(message, onToken, onDone, onReflection) {}
export async function getReviewItems() {}
export async function decideReviewItem(itemId, decision, options) {}
export async function getKgNodes(layer, includeArchived) {}
export async function getKgNode(nodeId) {}
export async function getKgGraph() {}
export async function getPruneCandidates() {}
export async function archiveNode(nodeId, reason) {}
export async function boostNode(nodeId, newImportance) {}
export async function getNotifications() {}
export async function consumeNotification(id) {}
```

---

## EventBus 使用方式

```javascript
// 发送事件
window.dispatchEvent(new CustomEvent('cyber:事件名', { detail: { /* payload */ } }));

// 监听事件
window.addEventListener('cyber:事件名', (e) => { const payload = e.detail; });
```

---

## 各面板监听/发送的事件

### 对话框面板（dialogue.js）

**监听**（来自 Phaser）：
- `cyber:npc:interact` → 打开对话框，`{ npcId, npcName }`
- `cyber:object:interact` → 当 objectId 不是 "taskboard" 时，打开对话框携带 contextHint，`{ objectId, contextHint }`

**发送**：
- 打开时：`cyber:panel:opened { panelId: "dialogue" }`
- 关闭时：`cyber:panel:closed { panelId: "dialogue" }`

**交互规则**：
- `contextHint` 存在时作为本轮对话的系统消息前缀，连同用户消息传给 `chatStream()`
- streaming 时显示 `|` 光标（8fps 闪烁），完成后消失
- `reflection` 触发时右上角显示「💡 正在更新认知图谱…」，3 秒后消失
- 点击 X 或按 Esc 关闭

---

### 房间入口确认（room-entry，可在 dialogue.js 或独立文件）

**监听**：`cyber:door:approach { targetScene, roomName, modeDescription }`

**显示**：约 320×120px 浮窗，居中偏上，`roomName + modeDescription + Y/N 按钮`

**发送**：
- 按 Y：`cyber:door:confirmed { targetScene }` + `cyber:panel:closed { panelId: "room-entry" }`
- 按 N / Esc：`cyber:door:cancelled` + `cyber:panel:closed { panelId: "room-entry" }`

---

### 任务板面板（taskboard.js）

**监听**：`cyber:object:interact` 且 `objectId === "taskboard"`（只响应这一种，GymScene 物件由对话框处理）

**逻辑**：
- 打开时发送 `cyber:panel:opened { panelId: "taskboard" }`
- 调用 `getReviewItems()`，展示待审批条目
- 每条展示 `sourceMode` 映射的来源标签 + 内容摘要
- 空状态展示提示文案
- 点击某条目打开 review.js 面板

---

### /review 审批面板（review.js）

**四种状态**：LOG 路由 / KG 路由有相似节点 / KG 路由无相似节点 / 空状态

**交互**：
- importance 滑块 1–10，像素风样式
- 键盘快捷键：Y（approved_kg）/ N（rejected）/ s（approved_log）/ q（退出）
- 提交调用 `decideReviewItem()`
- 全部处理完发送 `cyber:review:done { processedCount: N }`

---

### /kg 知识图谱面板（kg.js）

**布局**：三列（Id / Ego / Superego），Tab 激活态用对应层级色

**节点卡片**：importance 色标（1–3 灰、4–6 白、7–8 黄、9–10 红）+ 标题 + 描述预览

**功能**：归档节点灰度，默认隐藏，「显示已归档」开关控制；点击节点展开完整 evidence

---

### /prune 老化管理面板（prune.js）

**布局**：
- 顶部三类统计卡片：候选归档（critical）/ 接近阈值（warning）/ 健康（healthy）
- 逐条展示候选节点 + stalenessScore + 三个按钮（归档 / 提升 importance / 跳过）

**交互**：操作后实时移除已处理条目；全部完成展示总结

---

### HUD 顶部栏（index.html + hud.css）

```html
<!-- 结构 -->
<div id="hud">
  <span id="hud-room">中央区</span>
  <span id="hud-badge" hidden>3</span>
</div>
```

**监听**：
- `cyber:scene:changed { roomName }` → 更新 `#hud-room` 文字
- `cyber:notification:badge { count }` → `count > 0` 时显示角标

**样式**：`position: fixed`，顶部薄条，不遮挡游戏主体

---

## sourceMode → 展示标签映射

| sourceMode | 展示标签 |
|------------|---------|
| `"health"` | `[健身房]` |
| `"work"` | `[办公室]` |
| `"study"` | `[学习室]` |
| `"cyber"` | `[赛博明翰]` |

---

## 目录结构

```
frontend/
├── index.html          ← 入口，加载 Phaser CDN + 所有面板 JS
├── client.js           ← API 封装 + USE_MOCK 开关
├── style/
│   ├── tokens.css      ← CSS 变量（7 个颜色 token）
│   ├── panels.css      ← 所有面板样式
│   └── hud.css         ← HUD 顶部栏样式
└── panels/
    ├── dialogue.js     ← 对话框 + 房间入口确认
    ├── taskboard.js    ← /review 条目列表
    ├── review.js       ← /review 逐条审批
    ├── kg.js           ← /kg 知识图谱
    └── prune.js        ← /prune 老化管理
```
