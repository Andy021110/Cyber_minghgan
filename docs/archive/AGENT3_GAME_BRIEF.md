# Agent 3：Phaser.js 游戏层开发者 · 任务简报

> 版本：2026-06-07  
> 执行人：Phaser.js 前端开发者  
> 依赖文档：`docs/TECH_SPEC.md`、`docs/AGENT2_DESIGN_BRIEF.md`

---

## 一、角色定位

**你是什么**：游戏世界的建造者。你的产出是用户打开页面后看到的第一层——像素场景、可行走的角色、会待机的 NPC、走进去会有反应的门洞。你的代码运行在 Phaser.js Canvas 上，覆盖在 HTML 功能面板的下方。

**你负责什么**：
- Phaser 项目配置与场景管理（`main.js`、`roomConfig.js`）
- 所有游戏场景的实现：WorldScene、GymScene 及 Phase 2 stub 场景
- 玩家角色：行走动画、碰撞检测、键盘输入
- NPC：待机动画、INTERACT 触发区
- 触发系统：从 Tilemap Object Layer 读取触发区，驱动 PROXIMITY 和 INTERACT 两类行为
- 场景切换：淡入淡出动画 + `scene.start()`
- EventBus 发送侧：在正确时机 `dispatchEvent` 游戏事件
- EventBus 接收侧：监听 `cyber:panel:opened/closed`、`cyber:door:confirmed/cancelled` 并响应

**你不负责什么**：
- 不写任何 HTML 面板（对话框、/review、/kg、/prune 均属 Agent 4）
- 不写 CSS 样式（除了 `game/colors.js` 的颜色常量）
- 不实现任何 FastAPI 接口或数据请求（Agent 4 负责）
- 不制作或修改任何美术资产（Agent 2 负责，你只加载）
- 不决定游戏世界以外的任何 UI 交互逻辑

**与其他 Agent 的关系**：
- 上游：Agent 2 交付 Sprite Sheet + Tilemap 后，你替换占位资产
- 并行：Agent 4 监听你发出的 EventBus 事件并响应；你监听 Agent 4 发出的 EventBus 事件
- 唯一共享接口：`window` 上的 `CustomEvent`，双方不共享任何代码模块

---

## 二、启动前必读

**必读章节（TECH_SPEC.md）**：

| 章节 | 为什么要读 |
|------|-----------|
| 版本范围说明 | 明确 Phase 1 只实现 WorldScene + GymScene，其余是 stub |
| 第一章 1.3–1.4 | 技术栈选型和双层架构原则，理解你的代码在整体中的位置 |
| 第一章 1.6 | 像素风约束：`pixelArt: true`、`zoom: 2`、`image-rendering: pixelated` |
| **第二章全章** | 场景拓扑、房间布局、触发区类型、常量名表、Tilemap 规格——这是你代码的蓝图 |
| 第三章 3.2、3.6 | Sprite Sheet 帧规格（行顺序！）和像素渲染配置（含 `colors.js`） |
| **第四章全章** | EventBus 所有事件的名称、方向、payload——你发出和接收的合同 |
| 第六章 6.1–6.3 | 目录结构和资产路径约定，你的文件放哪里、怎么加载资产 |

**相关简报**：
- `docs/AGENT2_DESIGN_BRIEF.md`：了解 Agent 2 交付资产的格式和命名，以便正确加载

可以不读的：第五章（FastAPI 接口）——那是 Agent 4 的事。

---

## 三、依赖与启动条件

**现在可以立即开始的工作**（不依赖任何人）：

```
✅ 项目结构搭建（frontend/ 目录，index.html 骨架）
✅ Phaser 配置（main.js + roomConfig.js 数据驱动注册）
✅ 占位资产版 WorldScene（纯色矩形代替 Tilemap，圆形代替角色）
✅ 玩家键盘移动 + 碰撞检测（先用矩形碰撞体）
✅ 触发区检测系统（PROXIMITY + INTERACT 逻辑）
✅ EventBus 发送和接收骨架（事件名和 payload 已在 TECH_SPEC 定义）
✅ 场景切换动画（淡入淡出）
✅ Phase 2 stub 场景（空文件，符合 roomConfig.js 注册格式）
```

**等 Agent 2 交付后才能完成的工作**：

| 等待内容 | 解锁的任务 |
|---------|-----------|
| `player.png` Sprite Sheet | 玩家角色帧动画（替换矩形占位） |
| `npc_cyber_v*.png` | 赛博明翰 NPC 动画 |
| `npc_health.png` | 健康管家 NPC 动画 |
| `world.tmj` + `interior.png` | WorldScene 真实地图渲染 |
| `gym.tmj` | GymScene 真实地图渲染 |
| `obj-taskboard-*.png` | 任务板物件两状态切换 |

**与 Agent 4 的关系**：不存在硬性依赖。你发 EventBus 事件，Agent 4 接收；Agent 4 发 EventBus 事件，你接收。双方可以独立开发、独立测试（用 `window.dispatchEvent` 手动触发对方事件来模拟）。

---

## 四、任务清单

任务按实现顺序排列，前面的任务是后面任务的基础，不可乱序。

---

### G1：项目结构 + Phaser 配置
**产出**：`frontend/game/main.js`、`frontend/game/roomConfig.js`  
**验收标准**：
- Phaser 配置含 `pixelArt: true`、`zoom: 2`
- 场景通过 `roomConfig.js` 数组注册，不在 `main.js` 硬编码场景类
- `roomConfig.js` 已包含全部四个场景条目，Phase 2 场景标注 `phase: 2`

```javascript
// roomConfig.js 结构示例（必须遵守）
export const ROOM_CONFIG = [
  { key: 'WorldScene',  sceneClass: WorldScene,  label: '中央区', phase: 1 },
  { key: 'GymScene',    sceneClass: GymScene,    label: '健身房', phase: 1 },
  { key: 'OfficeScene', sceneClass: OfficeScene, label: '办公室', phase: 2 },
  { key: 'StudyScene',  sceneClass: StudyScene,  label: '学习室', phase: 2 },
];
```

---

### G2：颜色常量文件
**产出**：`frontend/game/colors.js`  
**验收标准**：包含 TECH_SPEC 第一章 1.5 的全部 7 个色值，以 Phaser 接受的 `0xRRGGBB` 格式定义（CSS 变量在 Canvas 里无效）

---

### G3：占位资产版 WorldScene
**产出**：`frontend/game/scenes/WorldScene.js`  
**验收标准**：
- 用纯色矩形代替 Tilemap，标注各房间区域边界
- 玩家出生点在中央区
- 场景加载完成后发送 `cyber:scene:changed { sceneKey: 'WorldScene', roomName: '中央区' }`

---

### G4：玩家移动与碰撞
**产出**：`frontend/game/objects/Player.js`  
**验收标准**：
- WASD 或方向键四方向移动
- 移动时切换对应方向的 walk 动画帧（占位阶段用颜色变化代替）
- 静止时播放 idle 动画
- 碰墙停止（碰撞体用矩形）
- 提供 `enableInput()` / `disableInput()` 方法供 EventBus 监听器调用

---

### G5：触发区检测系统
**产出**：`WorldScene.js` 和 `GymScene.js` 中的触发逻辑  
**验收标准**：
- 从 Tilemap Object Layer `"triggers"` 读取触发区（占位阶段用手写矩形代替）
- PROXIMITY：玩家进入区域自动触发，对应 `type` 为 `door_to_*` 时发送 `cyber:door:approach`
- INTERACT：玩家在区域内按 E，对应 NPC 发送 `cyber:npc:interact`，对应物件发送 `cyber:object:interact`
- Phase 2 门洞的 PROXIMITY 触发显示「即将开放」提示，不发送 `cyber:door:approach`

---

### G6：EventBus 接收侧
**产出**：`WorldScene.js` 中的事件监听逻辑  
**验收标准**：
- 监听 `cyber:panel:opened` → 调用 `player.disableInput()`
- 监听 `cyber:panel:closed` → 调用 `player.enableInput()`
- 监听 `cyber:door:confirmed` → 启动场景淡出动画，完成后 `this.scene.start(targetScene)`
- 监听 `cyber:door:cancelled` → 无额外操作（`panel:closed` 已恢复输入）
- 监听 `cyber:review:done` → 触发任务板物件的状态切换动效

---

### G7：场景切换动画
**产出**：`WorldScene.js` 及各专项场景的切换逻辑  
**验收标准**：
- 淡出：当前场景 camera 黑色遮罩淡入，300ms，完成后调用 `scene.start()`
- 淡入：新场景 `create()` 完成后 camera 遮罩淡出，300ms
- 切换完成后新场景发送 `cyber:scene:changed`

---

### G8：NPC 通用类
**产出**：`frontend/game/objects/NPC.js`  
**验收标准**：
- 接收 `npcId`、`spriteKey`、坐标作为参数
- 播放 idle 动画（占位阶段用颜色矩形）
- 在 NPC 周围创建 INTERACT 触发区，玩家按 E 发送 `cyber:npc:interact { npcId, npcName }`

---

### G9：GymScene 实现
**产出**：`frontend/game/scenes/GymScene.js`  
**验收标准**：
- 包含健康管家 NPC（使用 NPC 通用类）
- 包含体重日历和训练记录本两个 INTERACT 触发区，按 E 发送 `cyber:object:interact { objectId, contextHint }`
- 出口触发区（PROXIMITY）直接返回 WorldScene，不弹确认提示
- 场景加载完成后发送 `cyber:scene:changed { sceneKey: 'GymScene', roomName: '健身房' }`

---

### G10：Phase 2 Stub 场景
**产出**：`frontend/game/scenes/OfficeScene.js`、`StudyScene.js`  
**验收标准**：
- 仅含最小 `create()` 方法（显示「建设中」文字 + 返回 WorldScene 的出口触发区）
- 符合 `roomConfig.js` 注册格式，Phaser 可正常加载不报错

---

### G11：通知角标查询
**产出**：WorldScene `create()` 末尾的通知查询逻辑  
**验收标准**：
- 场景加载完成时，调用 `GET /api/notifications` 接口
- 根据未消费通知数量发送 `cyber:notification:badge { count }`
- 任务板物件根据 `count > 0` 切换 normal/active 贴图

---

### G12：资产替换（等 Agent 2 交付后）
**产出**：用真实 Sprite Sheet 和 Tilemap 替换所有占位资产  
**验收标准**：
- 角色动画帧顺序与 TECH_SPEC 第三章 3.2 行顺序完全一致
- Tilemap 从 `.tmj` 文件加载，触发区从 Object Layer `"triggers"` 读取（不再手写矩形）
- 碰撞从 `"collision"` 图层提取
- 视觉效果在 `pixelArt: true` + `zoom: 2` 下像素清晰无模糊

---

## 五、不在范围内

| 不做的事 | 原因 |
|---------|------|
| 写任何 HTML 面板或 CSS 样式（对话框、/review 等） | Agent 4 负责 |
| 实现任何 FastAPI 请求（对话、审批、KG 查询） | Agent 4 负责，Agent 3 只发 EventBus 事件 |
| 修改或处理任何美术资产文件 | Agent 2 负责，Agent 3 只加载 |
| 为 Phase 2 场景实现完整功能 | Phase 1 只需 stub，Phase 2 另行规划 |
| 实现 HUD 顶部栏（房间名、通知角标显示） | 属于 HTML 层，由 Agent 4 监听 `cyber:scene:changed` 后更新 |
| 自行新增 EventBus 事件名 | 事件清单是合同，新增须走上报机制 |

---

## 六、上报机制

工作中遇到以下情况时，**不要自行假设，填写上报模板提交给 Agent 1 判断**：

- TECH_SPEC 未定义的技术细节（如 Phaser config 的 `width`/`height` 数值）
- EventBus 事件的 payload 不满足实际需求，需要新增字段
- Agent 2 的资产格式与 TECH_SPEC 第三章不符，不确定如何处理
- 发现 EventBus 合同（第四章）与 Agent 4 实际实现有出入

**上报方式**：在 `docs/OPEN_QUESTIONS.md` 末尾追加，使用以下模板：

```
## Q{编号} [Agent 3] [{日期}]
**问题**：
**背景**：
**我的猜测**：
**影响范围**：
**紧急程度**：高 / 中 / 低
**状态**：⏳ 待解答
```

**等待解答期间继续推进不受影响的任务**。Agent 3 的大部分任务可以用占位资产并行推进，只有 G12（资产替换）需要等 Agent 2，不要因为单个问题停工。

---

