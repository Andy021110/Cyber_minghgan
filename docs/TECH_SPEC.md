# 赛博明翰前端 · 技术规范文档

> 版本：2026-06-07  
> 作者：架构师（用户 + Claude）  
> 用途：所有执行 Agent 的工作基准，先读此文档再开工

---

## 版本范围说明

> **执行 Agent 在实现任何功能前，先确认它属于哪个 Phase。Phase 1 以外的内容不实现，但架构需要为后续 Phase 预留扩展接口。**

| Phase | 内容 | 状态 |
|-------|------|------|
| **Phase 1（本文档范围）** | 赛博明翰 NPC（中央区）+ 健康管家（健身房）+ /review / /kg / /prune 面板 + AI 对话 | **实现** |
| **Phase 2** | 工作助手（办公室）、学习助手（学习室）及后续新 workspace | 架构预留，不实现 |
| **Phase 3** | 赛博明翰和他的朋友们（独立社交地图，多用户只读互访） | 架构预留一个封闭门洞，不实现 |

**Phase 2 预留方式**：房间和场景通过配置数组注册（见 2.1），加新房间只需加一条 config，不改现有代码。  
**Phase 3 预留方式**：WorldScene Tilemap 右下角保留一个封闭门洞（视觉上存在但不可交互），Phase 3 时打开接入社交地图。

---

## 第一章：已对齐决策

> 本章列出所有不再需要讨论的决策。执行 Agent 遇到相关问题时，以此为准，不需要再提问或自行猜测。

---

### 1.1 产品形态与 MVP 范围

| 决策项 | 结论 |
|--------|------|
| 应用形态 | 本地 Web 应用，浏览器打开，部署后对外提供 URL |
| MVP 用户模型 | **单用户 Mode A**：其他人访问的是「用户自己的赛博明翰」，共用同一个 KG，不需要注册/登录/多账号 |
| 后续扩展方向 | 多用户（每人独立 KG）、移动端、外部 API 接入——均不在 MVP 范围内，架构预留接口但不实现 |

**MVP 的边界含义（对 Agent 4 尤其重要）**：不需要做 session、不需要做用户表、不需要做 auth 中间件。KG 路径固定为用户本地文件，FastAPI 启动后直接可用。

---

### 1.2 空间设计方案

**已选定：单一住宅 + 多专项房间**

游戏世界是一栋像素风的房子，玩家在房间之间自由行走。每个房间对应一个专项工作空间，进入后触发对应管家 NPC。

| 房间 | 专项管家 | 触发功能 |
|------|----------|----------|
| 中央活动区 | 赛博明翰（主 NPC） | 自由对话、/review 任务板入口 |
| 健身房 | 健康管家 | 健康数据对话、健康趋势查看 |
| 办公室 | 工作助手 | 工作规划对话 |
| 学习室 | 学习助手 | 学习记录对话 |

**关于「矿洞 / 农场 / 小镇」三层空间映射**：  
Id / Ego / Superego 是 KG 节点的**数据分层标签**，不是玩家导航的游戏地点。`PRODUCT_ALIGNMENT.md` 里的三层空间映射不体现在游戏世界里，**只作为 `/kg` 知识图谱面板内部的视觉分区风格**——力导向图里三个层级的节点区域可以沿用矿洞/农场/小镇的色温和氛围词。游戏世界保持单一住宅方案。

---

### 1.3 技术栈

| 层 | 技术选型 | 说明 |
|----|----------|------|
| 游戏世界层 | **Phaser.js 3** | 渲染像素场景、角色行走、NPC 碰撞检测、交互触发 |
| 功能面板层 | **原生 HTML + CSS + 轻量 JS** | 对话框、/review、/kg、/prune 等功能面板，叠加在 Phaser canvas 上方 |
| 两层通信 | **EventBus（自定义事件总线）** | Phaser 触发游戏事件 → HTML 面板响应；HTML 面板关闭 → Phaser 恢复控制 |
| 后端 | **FastAPI（Python）** | 包装现有 `CyberBrainStore` 和 pipeline，提供 REST 接口 |
| AI 对话 | **Server-Sent Events（SSE）** | streaming 输出，前端逐字渲染 |
| 构建工具 | 暂不引入（原生 ES Module + 静态文件服务）| P0 阶段不需要打包，P1 后视资源量决定是否引入 Vite |

**不引入的技术**：React / Vue / Angular（过重，像素风 UI 用原生 CSS 更直接）；WebSocket（SSE 已满足单向 streaming 需求）；TypeScript（MVP 阶段不引入额外编译链路）。

---

### 1.4 前端双层架构原则

```
┌─────────────────────────────────────────┐
│           浏览器视口                      │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │   HTML/CSS 功能面板层（z-index 高）│   │
│  │   对话框 / /review / /kg / /prune │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │   Phaser.js canvas 层             │   │
│  │   游戏世界、角色、NPC、场景        │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**核心原则**：
- Phaser canvas 始终存在于底层，功能面板以 `position: fixed` 叠加其上
- 面板打开时，Phaser 暂停角色输入（不暂停渲染，背景游戏世界保持可见）
- 面板关闭时，Phaser 恢复角色输入
- 两层之间**只通过 EventBus 通信**，不直接互相调用函数

---

### 1.5 色彩规范（Design Tokens）

所有颜色以 CSS 变量形式定义，前端直接引用变量名，不硬编码色值。

```css
:root {
  --color-bg:          #0d1117;  /* 游戏世界底色 */
  --color-card-bg:     #161b22;  /* 功能面板底色 */
  --color-border:      #30363d;  /* 边框 / 分割线 */
  --color-text:        #c9d1d9;  /* 正文主色 */

  --color-id:          #e05c5c;  /* Id 层 / 危险 / 警告 */
  --color-ego:         #3fb950;  /* Ego 层 / 成功 / 写入 */
  --color-superego:    #f0a500;  /* Superego 层 / 提示 */
}
```

---

### 1.6 像素风硬性约束

以下约束适用于所有前端实现（游戏层和面板层均遵守）：

| 属性 | 规范 |
|------|------|
| 圆角 | 0px，最多 2px，谨慎使用 |
| 阴影 | 像素化 `drop-shadow`，偏移 2–4px，模糊半径 0px |
| 动画 | 帧动画，8fps，不使用贝塞尔曲线缓动 |
| 图标 | 16×16 或 32×32 像素栅格，手绘像素风 PNG |
| 字体（标题）| `Press Start 2P`（不支持中文，仅用于英文标题/标识）|
| 字体（内容）| `Noto Sans Mono` 或系统等宽字体（中英文均用） |

---

### 1.7 后端现状与 MVP 改动范围

**现状（对 Agent 4 说明）**：

| 组件 | 现状 | MVP 所需改动 |
|------|------|-------------|
| `CyberBrainStore` | `__init__` 已接受 `kg_path` 参数 | **无需改动** |
| `handle_review()` / `handle_kg()` / `handle_prune()` | 直接调用 `input()` / `print()`，无法被 API 调用 | **I/O 解耦**：改为接收参数、返回数据结构 |
| `decision_log.py` | 路径为模块级硬编码常量 | **参数化**：改为函数参数传入 |
| `_reflection_cycle()` / `run()` | 主 REPL 循环，含 `input()` 交互 | **拆分**：将业务逻辑与 I/O 分离，供 FastAPI 调用 |

**改动优先级**：I/O 解耦是 FastAPI 封装的前置条件，必须先完成再写路由。不允许在 FastAPI handler 里直接调用含 `input()` 的函数。

---

## 第二章：空间与房间结构

> 本章定义游戏世界的场景拓扑、房间用途、NPC 位置、触发区域类型。  
> **Agent 2**：以 2.2 的布局草图为空间参考，具体构图和装饰自由发挥。  
> **Agent 3**：以 2.5 的常量名表为代码中所有场景/房间/NPC/物件的标识符标准。

---

### 2.1 场景拓扑

游戏世界由 **1 个主世界场景 + 3 个专项房间场景** 构成，Phaser 以多场景方式管理。

```
┌──────────────┐     进入门洞      ┌───────────────┐
│  WorldScene  │ ───────────────▶ │   GymScene    │
│  （主世界）   │ ◀─────────────── │   （健身房）   │
│              │     走到出口      └───────────────┘
│              │
│              │ ───────────────▶ ┌───────────────┐
│              │ ◀─────────────── │  OfficeScene  │
│              │                  │  （办公室）    │
│              │                  └───────────────┘
│              │
│              │ ───────────────▶ ┌───────────────┐
│              │ ◀─────────────── │  StudyScene   │
└──────────────┘                  │  （学习室）    │
                                  └───────────────┘
```

**场景切换方式**：玩家走入门洞触发区 → HTML 面板显示进入确认提示 → 玩家按 Y → Phaser 淡出 + `scene.start(目标场景)` → 玩家出现在目标场景的入口位置。按 N 则关闭提示，玩家继续在当前场景行走。

**⚠️ 可扩展性约束（Agent 3 必读）**：场景列表必须通过配置数组注册，不得在 `main.js` 里硬编码场景类。标准写法：

```javascript
// frontend/game/main.js
import { ROOM_CONFIG } from './roomConfig.js';

const config = {
  scene: ROOM_CONFIG.map(r => r.sceneClass),  // 从配置数组读取，加新房间只改 roomConfig.js
};
```

```javascript
// frontend/game/roomConfig.js  ← Phase 2 只需在这里加一行
export const ROOM_CONFIG = [
  { key: 'WorldScene',  sceneClass: WorldScene,  label: '中央区',   phase: 1 },
  { key: 'GymScene',    sceneClass: GymScene,    label: '健身房',   phase: 1 },
  { key: 'OfficeScene', sceneClass: OfficeScene, label: '办公室',   phase: 2 },  // Phase 2，stub
  { key: 'StudyScene',  sceneClass: StudyScene,  label: '学习室',   phase: 2 },  // Phase 2，stub
];
```

Phase 2 的场景文件可以是空 stub（只有 `create()` 方法），Phase 1 的门洞触发区对 phase > 1 的场景显示「即将开放」提示而非进入。

---

### 2.2 主世界布局（WorldScene）

```
┌────────────────────────────────────────────┐
│  ╔══════════╗           ╔══════════╗       │
│  ║  健身房  ║           ║  学习室  ║       │
│  ║  [门洞]  ║           ║  [门洞]  ║       │
│  ╚══════════╝           ╚══════════╝       │
│                                            │
│         ┌──────────────────┐               │
│         │   中央活动区      │               │
│         │  [赛博明翰 NPC]  │               │
│         │  [任务板]        │               │
│         └──────────────────┘               │
│                                            │
│  ╔══════════╗           ╔══════════╗       │
│  ║  办公室  ║           ║  [预留]  ║       │
│  ║  [门洞]  ║           ║          ║       │
│  ╚══════════╝           ╚══════════╝       │
└────────────────────────────────────────────┘
```

**空间说明**：
- 中央活动区是玩家初始位置，赛博明翰 NPC 和任务板都在这里
- 四个角的房间通过门洞与中央区连通，玩家走进门洞区域触发进入提示
- 右下角预留区 MVP 不实现，Tilemap 可画成封闭房间（门洞不可交互）

---

### 2.3 各专项房间布局

每个专项房间的结构相同：**入口区 + NPC 站立区 + 可交互物件区 + 出口区**。

| 场景 | NPC | 可交互物件 |
|------|-----|-----------|
| GymScene | 健康管家 | 体重日历、训练记录本 |
| OfficeScene | 工作助手 | 任务白板（Phase 2 stub） |
| StudyScene | 学习助手 | 书架（Phase 2 stub） |

**GymScene 物件交互行为（Phase 1）**：体重日历和训练记录本均触发与健康管家的对话面板，携带不同的上下文提示（`contextHint` 字段通过 `cyber:object:interact` 事件传入，HTML 层将其作为对话的首条系统消息）。

| 物件 | `objectId` | `contextHint` |
|------|-----------|---------------|
| 体重日历 | `"weight_calendar"` | `"用户想查看体重趋势"` |
| 训练记录本 | `"training_log"` | `"用户想回顾训练记录"` |

> 这意味着 `cyber:object:interact` 事件的 payload 需要增加可选字段 `contextHint?: string`（见第四章 4.2 对应更新）。

**出口位置**：每个专项房间的出口触发区位于入口对面，玩家走到出口区自动返回 WorldScene（不需要确认提示，直接过渡）。

---

### 2.4 触发区域类型

游戏中有两类触发区，行为不同：

| 类型 | 触发方式 | 行为 | 示例 |
|------|----------|------|------|
| **PROXIMITY** | 玩家走入区域时自动触发 | 弹出 HTML 提示（进入房间确认） | 门洞进入提示 |
| **INTERACT** | 玩家走入区域后按 **E** | 打开对应功能面板 | NPC 对话、任务板、物件 |

所有触发区均在 Tilemap 的 Object Layer 里定义，Phaser 加载时读取坐标和 `type` 属性，不硬编码坐标。

> **Phase 1 说明**：PROXIMITY 类型在 Phase 1 只用于门洞进入提示，不用于其他自动触发场景。所有其他交互均为 INTERACT 类型（需要按 E）。

---

### 2.5 场景与实体名称常量

以下常量名是所有 Agent 的统一标识符，**代码、Tilemap JSON、EventBus 事件名均使用这套名称，不得自行命名**。

**场景名（Phaser scene key）**

| 常量 | 值 | 说明 |
|------|-----|------|
| `SCENE_WORLD` | `"WorldScene"` | 主世界 |
| `SCENE_GYM` | `"GymScene"` | 健身房 |
| `SCENE_OFFICE` | `"OfficeScene"` | 办公室 |
| `SCENE_STUDY` | `"StudyScene"` | 学习室 |

**NPC 标识符**

| 常量 | 值 | 所在场景 |
|------|-----|---------|
| `NPC_CYBER` | `"cyber_minghan"` | WorldScene |
| `NPC_HEALTH` | `"health_coach"` | GymScene |
| `NPC_WORK` | `"work_assistant"` | OfficeScene |
| `NPC_STUDY` | `"study_assistant"` | StudyScene |

**可交互物件标识符**

| 常量 | 值 | 所在场景 | 触发功能 |
|------|-----|---------|---------|
| `OBJ_TASKBOARD` | `"taskboard"` | WorldScene | 打开 /review 任务板面板 |
| `OBJ_WEIGHT_CAL` | `"weight_calendar"` | GymScene | 健康趋势图表 |
| `OBJ_TRAINING_LOG` | `"training_log"` | GymScene | 训练日志 |
| `OBJ_WHITEBOARD` | `"whiteboard"` | OfficeScene | TBD |
| `OBJ_BOOKSHELF` | `"bookshelf"` | StudyScene | TBD |

**触发区 type 值（Tiled Object Layer 属性）**

| type 值 | 含义 |
|---------|------|
| `"door_to_gym"` | 走入触发进入健身房提示 |
| `"door_to_office"` | 走入触发进入办公室提示 |
| `"door_to_study"` | 走入触发进入学习室提示 |
| `"exit_to_world"` | 走入自动返回主世界 |
| `"spawn"` | 玩家出生点（每个场景各一个） |

---

### 2.6 Tilemap 技术规格

| 参数 | 规格 | 说明 |
|------|------|------|
| 图块尺寸 | 16×16 px | 所有 Tileset 的基础网格 |
| Tilemap 格式 | Tiled JSON（`.tmj`）+ PNG Tileset | Phaser 3 直接支持 |
| Object Layer 名称 | `"triggers"` | Phaser 从此层读取所有触发区坐标和 type |
| 碰撞层名称 | `"collision"` | Phaser 从此层提取碰撞 tile |

---

## 第三章：资产规范

> 本章主要面向 **Agent 2（像素美术 + UI 设计）**。  
> 分为两类要求：**技术信封**（代码依赖，不可更改）和**创意自由区**（方向参考，设计师自由发挥）。  
> 技术信封约束的是「格子的尺寸和标签」，格子里画什么完全是设计师的事。

---

### 3.1 技术信封 vs 创意自由区

| 属于技术信封（必须遵守） | 属于创意自由区（自由发挥） |
|--------------------------|---------------------------|
| Sprite Sheet 帧尺寸和行列排列顺序 | 角色外形、配色、服装、风格 |
| 文件命名规范 | 房间装饰、物件摆放密度、氛围 |
| KG 层级语义色（Id/Ego/Superego 三色） | 地板、墙壁、家具的具体像素设计 |
| Tileset 图块尺寸（16×16px） | 图块的纹理、色调、视觉风格 |
| 可交互物件两种状态（normal / active）| 物件的具体外形和动效设计 |
| PNG 透明背景、1x + 2x 两份 | 赛博明翰 NPC 三版的形象方向 |

---

### 3.2 角色 Sprite Sheet

**帧规格（所有角色共用，严格一致）**

| 参数 | 规格 |
|------|------|
| 单帧尺寸 | 32×48 px |
| 背景 | PNG 透明背景 |
| 排列方式 | 行 = 动作，列 = 帧，从左到右 |
| 最大列数 | 4 列（最长动作 4 帧，不足 4 帧的用空白帧补齐） |

**行顺序（Agent 3 按此索引加载动画，顺序不可改）**

| 行号 | 动作名 | 帧数 | 说明 |
|------|--------|------|------|
| 0 | `idle` | 4 | 站立待机 |
| 1 | `walk_down` | 4 | 向下走 |
| 2 | `walk_up` | 4 | 向上走 |
| 3 | `walk_left` | 4 | 向左走 |
| 4 | `walk_right` | 4 | 向右走 |
| 5 | `interact` | 2 | 交互动作，第 3、4 列留空白帧 |

**整张 Sprite Sheet 尺寸**：128×288 px（4 列 × 6 行 × 32×48）

**角色清单**

| 文件名 | 角色 | 版本数 |
|--------|------|--------|
| `player.png` | 玩家角色 | 1 |
| `npc_cyber_v1.png` | 赛博明翰（镜像版玩家方向） | 3 版各一文件 |
| `npc_cyber_v2.png` | 赛博明翰（设计师自由发挥 A） | — |
| `npc_cyber_v3.png` | 赛博明翰（设计师自由发挥 B） | — |
| `npc_health.png` | 健康管家 | 1 |
| `npc_work.png` | 工作助手 | 1 |
| `npc_study.png` | 学习助手 | 1 |

> 三版赛博明翰帧规格完全相同，仅视觉设计不同。对话框里的角色头像直接取 `idle` 行第 0 帧放大 2x，无需额外绘制肖像图。

---

### 3.3 Tileset 规格

| 参数 | 规格 |
|------|------|
| 图块尺寸 | 16×16 px |
| 格式 | PNG 透明背景，Tilemap 使用 **`.tmj`** 格式（Phaser 3 原生支持），Tileset 使用 **`.tsj`** 格式 |
| 内容 | 地板、墙壁、门洞、装饰物图块 |
| 推荐宽度 | 256 px（16 列），高度不限 |

**各场景氛围方向（创意参考，不作硬约束）**

> ⚠️ 以下氛围词是**视觉美术方向**，与 Id / Ego / Superego 层级颜色（红/绿/橙）无关。Id/Ego/Superego 是 KG 数据标签，不映射到任何游戏场景。设计师不要把层级色用于场景装饰。

| 场景 | 氛围词 | 色温参考 |
|------|--------|---------|
| WorldScene（中央区） | 温暖、居家、熟悉 | 暖木色调 |
| GymScene | 活力、略偏功能性 | 中性偏冷 |
| OfficeScene | 专注、简洁 | 冷白偏蓝 |
| StudyScene | 安静、书卷气 | 暖黄偏橙 |

整体底色锁定在 `#0d1117` 附近，各房间在此基础上做色温微调。

---

### 3.4 可交互物件规格

每个物件提供 **normal**（普通）和 **active**（激活/发光边框）两种状态，各自独立 PNG 文件。

> ⚠️ 物件 PNG 必须单独交付为独立文件，**不得嵌入 Tileset**。Tileset 只包含地板、墙壁、门洞等背景图块；可交互物件由 Phaser 作为独立 Sprite 加载，叠放在 Tilemap 上方。

| 物件 | 文件名前缀 | 尺寸 | 所在场景 |
|------|-----------|------|---------|
| 任务板 | `obj-taskboard` | 48×32 px | WorldScene |
| 体重日历 | `obj-weight-calendar` | 32×32 px | GymScene |
| 训练记录本 | `obj-training-log` | 16×32 px | GymScene |
| 任务白板 | `obj-whiteboard` | 48×48 px | OfficeScene |
| 书架 | `obj-bookshelf` | 48×48 px | StudyScene |

**文件命名**：`{前缀}-normal.png` / `{前缀}-active.png`，各提供 1x + 2x 两份（2x 文件加 `@2x` 后缀）。

示例：`obj-taskboard-normal.png`、`obj-taskboard-normal@2x.png`

---

### 3.5 功能图标规格（HTML/CSS 面板层）

| 图标 | 文件名 | 尺寸版本 | 用途 |
|------|--------|---------|------|
| 知识图谱 | `icon-kg` | 16 + 32 | /kg 入口 |
| 审批通过 | `icon-approve` | 16 | /review 操作按钮 |
| 审批拒绝 | `icon-reject` | 16 | /review 操作按钮 |
| 归档 | `icon-archive` | 16 + 32 | 节点归档状态 |
| 合并 | `icon-merge` | 16 | /prune merge |
| 老化（沙漏） | `icon-stale` | 16 | staleness 指示 |
| 设置 | `icon-settings` | 16 | 设置入口 |
| Id 层（火焰） | `icon-id` | 16 + 32 | 层级标识 |
| Ego 层（秤） | `icon-ego` | 16 + 32 | 层级标识 |
| Superego 层（眼睛） | `icon-superego` | 16 + 32 | 层级标识 |

**文件命名**：`icon-{name}-{size}.png`，例如 `icon-kg-32.png`。  
**格式**：PNG 透明背景，同时提供 SVG 版本（用于 CSS 直接引用）。

---

### 3.6 像素渲染设置（给 Agent 3 参考）

设计师出图是 1x 原始像素尺寸，代码层统一做 2x 放大以适配普通显示器，用以下方式保持像素清晰：

```javascript
// Phaser 游戏配置
const config = {
  pixelArt: true,   // 禁用抗锯齿，保持像素边缘清晰
  width: 720,       // 内部渲染宽度（显示宽度 = 720 × zoom = 1440px）
  height: 450,      // 内部渲染高度（显示高度 = 450 × zoom = 900px）
  zoom: 2,          // 整体放大 2x，像素保持清晰
};
```

canvas 内部渲染尺寸为 720×450px，经 zoom=2 放大后浏览器中实际显示为 1440×900px。

```css
/* HTML/CSS 面板层图片 */
img, canvas {
  image-rendering: pixelated;
}
```

> **重要**：`tokens.css` 中的 CSS 变量只在 **HTML/CSS 面板层**生效，Phaser Canvas 无法读取 CSS 变量。Agent 3 在 Phaser 场景内需要颜色时（如 HUD 文字、调试图形），使用以下硬编码常量，保持与 tokens.css 同步：

```javascript
// frontend/game/colors.js  ← Agent 3 维护，与 tokens.css 保持人工同步
export const COLORS = {
  BG:        0x0d1117,
  CARD_BG:   0x161b22,
  BORDER:    0x30363d,
  TEXT:      0xc9d1d9,
  ID:        0xe05c5c,
  EGO:       0x3fb950,
  SUPEREGO:  0xf0a500,
};
```

---

## 第四章：EventBus 事件清单

> 本章主要面向 **Agent 3（Phaser 游戏层）** 和 **Agent 4（HTML 面板层）**。  
> EventBus 是两层之间的唯一通信机制。Agent 3 负责发送游戏事件，Agent 4 负责发送面板事件，双方均监听对方的事件。  
> **此清单即合同：事件名、方向、payload 结构不得自行修改或新增，如需变更须更新本文档。**

---

### 4.1 实现方式

使用浏览器原生 `CustomEvent` + `window` 作为事件总线。Phaser 层和 HTML 层不需要共享模块，各自独立监听和发送。

**发送事件：**

```javascript
window.dispatchEvent(new CustomEvent('cyber:事件名', {
  detail: { /* payload */ }
}));
```

**监听事件：**

```javascript
window.addEventListener('cyber:事件名', (e) => {
  const payload = e.detail;
});
```

所有事件名均以 `cyber:` 为前缀，避免与浏览器或第三方库的事件名冲突。

---

### 4.2 Phaser → HTML 事件（游戏层触发，面板层响应）

#### `cyber:npc:interact`
玩家在 NPC 的 INTERACT 触发区内按下 E 键。

| 字段 | 类型 | 说明 |
|------|------|------|
| `npcId` | `string` | NPC 标识符，见第二章 2.5 常量表 |
| `npcName` | `string` | 显示名称，如 `"赛博明翰"` |

**HTML 层响应**：打开对话框面板，向 FastAPI 发起对话请求，传入 `npcId`。

---

#### `cyber:object:interact`
玩家在可交互物件的 INTERACT 触发区内按下 E 键。

| 字段 | 类型 | 说明 |
|------|------|------|
| `objectId` | `string` | 物件标识符，见第二章 2.5 常量表 |
| `contextHint` | `string?` | 可选，物件携带的对话上下文提示（GymScene 物件使用，见 2.3） |

**HTML 层响应**：根据 `objectId` 打开对应面板。

| `objectId` | 打开的面板 |
|------------|-----------|
| `"taskboard"` | /review 任务板面板 |
| `"weight_calendar"` | 健康趋势图表面板 |
| `"training_log"` | 训练日志面板 |

---

#### `cyber:door:approach`
玩家走入门洞的 PROXIMITY 触发区。

| 字段 | 类型 | 说明 |
|------|------|------|
| `targetScene` | `string` | 目标场景 key，如 `"GymScene"` |
| `roomName` | `string` | 显示名，如 `"健身房"` |
| `modeDescription` | `string` | 模式说明，如 `"进入健康管家模式"` |

**HTML 层响应**：显示房间入口确认提示（Y / N）。

---

#### `cyber:scene:changed`
Phaser 完成场景切换，新场景的 `create()` 执行完毕。

| 字段 | 类型 | 说明 |
|------|------|------|
| `sceneKey` | `string` | 新场景 key |
| `roomName` | `string` | 新场景显示名，如 `"中央区"` |

**HTML 层响应**：更新 HUD 顶部的当前房间名。

---

#### `cyber:notification:badge`
Phaser 在场景加载时查询后端，获取未消费通知数量。

| 字段 | 类型 | 说明 |
|------|------|------|
| `count` | `number` | 未消费通知数（0 表示清空角标） |

**HTML 层响应**：更新任务板物件上方的通知角标。

---

### 4.3 HTML → Phaser 事件（面板层触发，游戏层响应）

#### `cyber:panel:opened`
任何 HTML 面板打开时发送。

| 字段 | 类型 | 说明 |
|------|------|------|
| `panelId` | `string` | 面板标识符，见 4.4 面板 ID 表 |

**Phaser 层响应**：禁用玩家键盘移动输入，游戏世界继续渲染。

---

#### `cyber:panel:closed`
任何 HTML 面板关闭时发送。

| 字段 | 类型 | 说明 |
|------|------|------|
| `panelId` | `string` | 面板标识符 |

**Phaser 层响应**：重新启用玩家键盘移动输入。

---

#### `cyber:door:confirmed`
玩家在房间入口确认提示中按下 Y。

| 字段 | 类型 | 说明 |
|------|------|------|
| `targetScene` | `string` | 目标场景 key（从 `cyber:door:approach` 原样转发） |

**Phaser 层响应**：执行场景淡出动画，调用 `this.scene.start(targetScene)`。

---

#### `cyber:door:cancelled`
玩家在房间入口确认提示中按下 N。payload 为空。

**Phaser 层响应**：恢复玩家移动输入。

---

#### `cyber:review:done`
/review 面板完成本次所有审批。

| 字段 | 类型 | 说明 |
|------|------|------|
| `processedCount` | `number` | 本次处理的条目数 |

**Phaser 层响应**：触发任务板物件清空动效，重新查询通知数量。

---

### 4.4 面板 ID 表

| panelId | 对应面板 |
|---------|---------|
| `"dialogue"` | NPC 对话框 |
| `"room-entry"` | 房间入口确认提示 |
| `"taskboard"` | /review 任务板面板（条目列表） |
| `"review"` | /review 审批面板（逐条操作） |
| `"kg"` | /kg 知识图谱面板 |
| `"prune"` | /prune 老化管理面板 |

---

### 4.5 事件流示例

**玩家走近赛博明翰并开始对话：**

```
玩家按 E（Phaser 检测到 INTERACT 区）
  → Phaser 发送 cyber:npc:interact { npcId: "cyber_minghan", npcName: "赛博明翰" }
  → HTML 打开对话框，发送 cyber:panel:opened { panelId: "dialogue" }
  → Phaser 禁用移动输入
  → 对话进行中...
  → 玩家点击 X 关闭
  → HTML 发送 cyber:panel:closed { panelId: "dialogue" }
  → Phaser 重新启用移动输入
```

**玩家走入健身房门洞：**

```
玩家走入 PROXIMITY 触发区
  → Phaser 发送 cyber:door:approach { targetScene: "GymScene", roomName: "健身房", modeDescription: "进入健康管家模式" }
  → HTML 显示确认提示，发送 cyber:panel:opened { panelId: "room-entry" }
  → Phaser 禁用移动输入

  [按 Y]
  → HTML 发送 cyber:door:confirmed { targetScene: "GymScene" }
  → HTML 发送 cyber:panel:closed { panelId: "room-entry" }
  → Phaser 淡出，scene.start("GymScene")

  [按 N]
  → HTML 发送 cyber:door:cancelled
  → HTML 发送 cyber:panel:closed { panelId: "room-entry" }
  → Phaser 重新启用移动输入
```

---

## 第五章：FastAPI 接口契约

> 本章主要面向 **Agent 4（面板层 + 接口开发者）**。  
> 定义所有 HTTP 接口的路由、方法、请求体、响应体，以及对应的现有后端函数。  
> Agent 4 实现时以此为准；前端调用时以此为准。两者不一致时以本文档为准，并更新本文档。

---

### 5.1 基础规范

| 项目 | 规范 |
|------|------|
| URL 前缀 | 所有接口均以 `/api` 开头 |
| 数据格式 | 请求体和响应体均为 JSON，`Content-Type: application/json` |
| 流式响应 | 对话接口使用 SSE（Server-Sent Events），`Content-Type: text/event-stream` |
| 错误格式 | `{ "error": "描述字符串" }`，HTTP 状态码 4xx/5xx |
| CORS | 开发阶段允许 `localhost` 所有端口，生产部署时收紧 |
| 启动命令 | `uvicorn api.main:app --reload --port 8000` |

---

### 5.2 对话接口

#### `POST /api/chat`

向指定 NPC 发送一条消息，以 SSE 流式返回 AI 回复。

**请求体：**

```json
{
  "npcId": "cyber_minghan",
  "message": "你好"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `npcId` | `string` | NPC 标识符，见第二章 2.5 常量表 |
| `message` | `string` | 用户输入的消息内容 |

**响应（SSE 流）：**

```
data: {"type": "token", "content": "你"}
data: {"type": "token", "content": "好"}
data: {"type": "done", "fullText": "你好，我是赛博明翰。"}
data: {"type": "reflection", "triggered": false}
```

| SSE type | 说明 |
|----------|------|
| `token` | 流式输出的单个文字片段，前端逐字追加 |
| `done` | 回复完成，携带完整文本（用于日志或重发） |
| `reflection` | 本轮是否触发了反刍（`triggered: true` 时前端在对话框右上角显示「💡 正在更新认知图谱…」提示，3 秒后自动消失） |

**对应后端逻辑**：`CyberBrainStore` 的对话核心 + streaming 输出，对话历史维护在服务器内存中（单用户 MVP，无需 session 管理）。

---

#### `DELETE /api/chat/history`

清空当前对话历史，开启新一轮对话。

**响应：** `{ "cleared": true }`

---

### 5.3 /review 审批接口

#### `GET /api/review/items`

获取所有待审批条目（`status = "awaiting"`）。

**响应：**

```json
{
  "items": [ /* ReviewItem[] */ ],
  "count": 3
}
```

**对应后端函数**：`decision_log.read_awaiting()`

> **sourceMode 与房间的对应关系**（/review 面板展示来源标签时使用）：

| `sourceMode` | 来源房间 | 来源 NPC | 展示标签 |
|-------------|---------|---------|---------|
| `"health"` | 健身房 | 健康管家 | `[健身房]` |
| `"work"` | 办公室 | 工作助手 | `[办公室]` |
| `"study"` | 学习室 | 学习助手 | `[学习室]` |
| `"cyber"` | 中央区 | 赛博明翰 | `[赛博明翰]` |

---

#### `GET /api/review/count`

获取待审批条目数量，用于通知角标快速查询。

**响应：** `{ "count": 3 }`

---

#### `POST /api/review/items/{item_id}/decide`

对单条审批条目做出决策。

**请求体：**

```json
{
  "decision": "approved_kg",
  "userNote": "这条记录很准确",
  "importance": 7,
  "description": "用户在高压下倾向于回避问题"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `decision` | `string` | 是 | `"approved_kg"` / `"approved_log"` / `"rejected"` |
| `userNote` | `string` | 否 | 用户补充说明或拒绝理由 |
| `importance` | `number` | 仅 `approved_kg` 时 | 1–10，覆盖 AI 建议值 |
| `description` | `string` | 否 | 仅 `approved_kg` 时，用户修改后的节点描述 |

**响应：** `{ "success": true, "itemId": "..." }`

**对应后端函数**：`decision_log.resolve_approval()` + `CyberBrainStore.create_node()`（如果 `approved_kg`）

---

### 5.4 /kg 知识图谱接口

#### `GET /api/kg/nodes`

获取 KG 节点列表。

**Query 参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `layer` | `string` | 全部 | `"Id"` / `"Ego"` / `"Superego"` |
| `includeArchived` | `boolean` | `false` | 是否包含已归档节点 |

**响应：**

```json
{
  "nodes": [ /* KGNode[] */ ],
  "count": 42
}
```

**对应后端函数**：`CyberBrainStore.get_all_nodes()`，前端按 layer 过滤。

---

#### `GET /api/kg/nodes/{node_id}`

获取单个节点的完整详情（含 evidence 列表）。

**响应：** 单个 `KGNode` 对象（schema 见 5.7）

---

#### `GET /api/kg/graph`

获取力导向图数据（节点 + 连线）。

**响应：**

```json
{
  "nodes": [{ "id": "...", "label": "...", "layer": "Ego", "importance": 7 }],
  "links": []
}
```

> MVP 阶段 `links` 返回空数组，预留给未来有向边功能。

---

### 5.5 /prune 老化管理接口

#### `GET /api/prune/candidates`

获取老化评估结果，按严重程度分组。

**响应：**

```json
{
  "stats": {
    "critical": 2,
    "warning": 5,
    "healthy": 35
  },
  "candidates": [ /* PruneCandidate[] */ ]
}
```

每个 `PruneCandidate` 包含节点基本信息 + `stalenessScore`（staleness 计算值）。

**对应后端函数**：`CyberBrainStore` 的 staleness 计算逻辑（`days_since_last_access / importance`）。

---

#### `POST /api/prune/{node_id}/archive`

将节点标记为归档。

**请求体：** `{ "reason": "长期未被引用，内容已过时" }`

**响应：** `{ "success": true }`

**对应后端函数**：`CyberBrainStore.archive_node()`

---

#### `POST /api/prune/{node_id}/boost`

提升节点 importance，阻止老化。

**请求体：** `{ "newImportance": 8 }`

**响应：** `{ "success": true, "newImportance": 8 }`

**对应后端函数**：`CyberBrainStore.update_node()`

---

### 5.6 通知接口

#### `GET /api/notifications`

获取所有未消费通知。

**响应：**

```json
{
  "notifications": [ /* Notification[] */ ],
  "count": 2
}
```

**对应后端函数**：`decision_log.read_unconsumed_notifications()`

---

#### `POST /api/notifications/{id}/consume`

标记通知为已消费。

**响应：** `{ "success": true }`

**对应后端函数**：`decision_log.consume_notification()`

---

### 5.7 数据模型（Schema）

#### `KGNode`

```json
{
  "id":            "string（UUID hex）",
  "label":         "string",
  "layer":         "Id | Ego | Superego",
  "description":   "string",
  "importance":    "number（1–10）",
  "evidence":      ["string"],
  "createdAt":     "ISO 8601",
  "lastAccessed":  "ISO 8601",
  "archived":      "boolean",
  "archiveReason": "string | null"
}
```

#### `ReviewItem`

```json
{
  "id":             "string",
  "pendingId":      "string",
  "timestamp":      "ISO 8601",
  "sourceMode":     "health | study | work",
  "content":        "string",
  "rawEvidence":    "string",
  "proposedRoute":  "kg | log",
  "proposedLayer":  "Id | Ego | Superego | null",
  "aiRationale":    "string",
  "importance":     "number | null",
  "importanceNote": "string | null"
}
```

#### `Notification`

```json
{
  "id":        "string",
  "timestamp": "ISO 8601",
  "type":      "pending_ready | protocol_updated",
  "message":   "string"
}
```

#### `PruneCandidate`

```json
{
  "node":          "KGNode",
  "stalenessScore": "number（越高越需要处理）",
  "severity":      "critical | warning | healthy"
}
```

---

## 第六章：目录结构

> 本章面向所有执行 Agent。  
> 定义每个 Agent 的产出物应放置的位置，以及各目录的「所有权」——谁写、谁只读，防止合并冲突。

---

### 6.1 整体目录树

以下是在现有后端代码库基础上新增的完整目录结构：

```
元宝-明翰/
│
├── [现有后端文件，不移动]
│   ├── cyber_planner.py
│   ├── health_coach.py
│   ├── pipelines/
│   ├── decision_logs/
│   └── yuanbao_cyber_minghan_kg.json
│
├── api/                          # FastAPI 应用（Agent 4 所有）
│   ├── main.py                   # FastAPI app 入口，挂载所有 router
│   ├── schemas.py                # Pydantic 数据模型（对应第五章 5.7）
│   └── routes/
│       ├── chat.py               # /api/chat
│       ├── review.py             # /api/review/*
│       ├── kg.py                 # /api/kg/*
│       ├── prune.py              # /api/prune/*
│       └── notifications.py      # /api/notifications/*
│
└── frontend/                     # 静态 Web 应用根目录
    ├── index.html                # 入口页面（Agent 4 维护）
    │
    ├── style/                    # 样式（Agent 4 维护）
    │   ├── tokens.css            # CSS 变量（第一章 1.5 色彩规范）
    │   ├── panels.css            # 所有功能面板样式
    │   └── hud.css               # HUD 顶部栏样式
    │
    ├── game/                     # Phaser 游戏层（Agent 3 所有）
    │   ├── main.js               # Phaser 配置 + 场景注册 + 启动
    │   ├── scenes/
    │   │   ├── WorldScene.js
    │   │   ├── GymScene.js
    │   │   ├── OfficeScene.js
    │   │   └── StudyScene.js
    │   └── objects/
    │       ├── Player.js         # 玩家角色：行走、碰撞、触发检测
    │       └── NPC.js            # NPC 通用类：待机动画、INTERACT 区
    │
    ├── panels/                   # HTML 功能面板（Agent 4 所有）
    │   ├── dialogue.js           # NPC 对话框
    │   ├── taskboard.js          # /review 任务板入口面板
    │   ├── review.js             # /review 逐条审批面板
    │   ├── kg.js                 # /kg 知识图谱面板
    │   └── prune.js              # /prune 老化管理面板
    │
    ├── client.js                 # FastAPI 请求封装（Agent 4 所有）
    │
    └── assets/                   # 游戏资产（Agent 2 交付，Agent 3 只读）
        ├── sprites/
        │   ├── player.png
        │   ├── npc_cyber_v1.png
        │   ├── npc_cyber_v2.png
        │   ├── npc_cyber_v3.png
        │   ├── npc_health.png
        │   ├── npc_work.png
        │   └── npc_study.png
        ├── tilemaps/
        │   ├── world.tmj
        │   ├── gym.tmj
        │   ├── office.tmj
        │   └── study.tmj
        ├── tilesets/
        │   ├── interior.png
        │   └── interior.tsj
        ├── objects/
        │   ├── obj-taskboard-normal.png
        │   ├── obj-taskboard-active.png
        │   └── ...
        └── icons/
            ├── icon-kg-16.png
            ├── icon-kg-32.png
            └── ...
```

---

### 6.2 目录所有权表

| 目录 / 文件 | 所有者（写） | 读取者 | 说明 |
|-------------|-------------|--------|------|
| `api/` | Agent 4 | — | FastAPI 后端 |
| `frontend/game/` | Agent 3 | — | Phaser 场景和对象 |
| `frontend/panels/` | Agent 4 | — | HTML 功能面板 |
| `frontend/client.js` | Agent 4 | — | API 请求封装 |
| `frontend/style/tokens.css` | Agent 4 | Agent 3（变量名引用） | 色彩 Token |
| `frontend/style/panels.css` | Agent 4 | — | 面板样式 |
| `frontend/index.html` | Agent 4 | — | 加载所有脚本 |
| `frontend/assets/` | Agent 2（交付） | Agent 3（加载） | Agent 3 按文件名加载，不修改 |

**冲突预防原则**：Agent 3 的 `game/` 和 Agent 4 的 `panels/` 完全分离。唯一共享机制是 `window` 上的 `CustomEvent`，不涉及任何共享文件。

---

### 6.3 资产路径约定

Phaser 加载资产时使用相对于 `frontend/` 的路径：

```javascript
// Sprite Sheet
this.load.spritesheet('player',        'assets/sprites/player.png',       { frameWidth: 32, frameHeight: 48 });
this.load.spritesheet('cyber_minghan', 'assets/sprites/npc_cyber_v1.png', { frameWidth: 32, frameHeight: 48 });

// Tilemap
this.load.tilemapTiledJSON('world', 'assets/tilemaps/world.tmj');
this.load.image('tileset-interior',  'assets/tilesets/interior.png');

// 可交互物件
this.load.image('obj-taskboard-normal', 'assets/objects/obj-taskboard-normal.png');
this.load.image('obj-taskboard-active', 'assets/objects/obj-taskboard-active.png');
```

路径中的文件名必须与第三章 3.2–3.5 的命名规范完全一致，Agent 3 不得自行改名。

---

### 6.4 本地开发启动

两个终端并行启动：

```bash
# 终端 1：FastAPI 后端
uvicorn api.main:app --reload --port 8000

# 终端 2：前端静态文件服务
cd frontend
python -m http.server 3000
```

浏览器访问 `http://localhost:3000`，前端通过 `http://localhost:8000/api/*` 调用后端。

> **KG 文件路径约定**：FastAPI 启动时以项目根目录（`元宝-明翰/`）为工作目录。`api/main.py` 中使用 `Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"` 作为 KG 路径，`decision_logs/` 同理。不要使用相对路径 `./`，避免因工作目录不同导致文件找不到。
> 
> **全局实例约定**：FastAPI 应用启动时创建单个全局 `CyberBrainStore` 实例和单个全局 `logs_dir` 路径，所有路由复用，不在每次请求时重新初始化。

---
