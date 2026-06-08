# 游戏层开发上下文（供 Agent 3 / WorkBuddy 游戏开发任务使用）

> 本文件摘录自 TECH_SPEC.md，覆盖 Phaser.js 游戏层开发所需的全部规格。

---

## Phase 范围

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1（当前） | WorldScene + GymScene + EventBus 发送/接收 | **实现** |
| Phase 2 | OfficeScene、StudyScene | stub 空文件，不实现功能 |
| Phase 3 | 社交地图 | 预留封闭门洞，不实现 |

---

## 技术栈

- **游戏引擎**：Phaser.js 3（CDN 加载）
- **语言**：原生 ES Module，无打包工具
- **通信**：`window.dispatchEvent` / `window.addEventListener`（CustomEvent EventBus）

**Phaser 配置（必须使用以下值）：**

```javascript
const config = {
  type: Phaser.AUTO,
  pixelArt: true,           // 必须开启，关闭会导致像素模糊
  width: 720,               // 内部分辨率
  height: 450,              // 内部分辨率
  zoom: 2,                  // 显示分辨率 = 1440 × 900px
  parent: 'game-container', // 必须与 index.html 中 <div id="game-container"> 一致
  backgroundColor: '#0d1117',
  physics: { default: 'arcade', arcade: { debug: false } },
  scene: ROOM_CONFIG.map(r => r.sceneClass),
};
```

**CDN 引入（index.html 中）：**

```html
<script src="https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js"></script>
```
```

---

## 像素风硬性约束

| 属性 | 规范 |
|------|------|
| 圆角 | 0px（最多 2px） |
| 阴影 | 像素化 drop-shadow，偏移 2–4px，模糊 0px |
| 动画帧率 | 8fps |
| 图标尺寸 | 16×16 或 32×32 像素栅格 |
| CSS 字体（标题） | `Press Start 2P` |
| CSS 字体（内容） | `Noto Sans Mono` |
| Canvas 渲染 | `image-rendering: pixelated` |

---

## 场景拓扑（必须用 roomConfig.js 数组注册）

```javascript
// frontend/game/roomConfig.js
export const ROOM_CONFIG = [
  { key: 'WorldScene',  sceneClass: WorldScene,  label: '中央区',   phase: 1 },
  { key: 'GymScene',    sceneClass: GymScene,    label: '健身房',   phase: 1 },
  { key: 'OfficeScene', sceneClass: OfficeScene, label: '办公室',   phase: 2 }, // stub
  { key: 'StudyScene',  sceneClass: StudyScene,  label: '学习室',   phase: 2 }, // stub
];
```

**绝对禁止**在 `main.js` 里硬编码场景类列表。

---

## 主世界布局（WorldScene）

画布内部分辨率 720×450px，各元素占位坐标参考（开发阶段用矩形占位，坐标可微调）：

```
canvas: 720 × 450px（内部坐标，zoom:2 后显示为 1440×900）

房间矩形占位（x, y, width, height）：
  健身房门洞区域：    (  30, 20, 140, 100)   左上角
  学习室门洞区域：    ( 540, 20, 140, 100)   右上角
  中央活动区：        ( 200,150, 320, 150)   中心
  办公室门洞区域：    (  30,330, 140, 100)   左下角
  Phase3 预留门洞：   ( 540,330, 140, 100)   右下角（不可交互）

NPC 与物件位置（世界坐标）：
  赛博明翰 NPC：      (360, 225)   中央区中心
  任务板：            (280, 200)   NPC 左侧
  玩家出生点：        (360, 280)   中央区略下方

触发区矩形（PROXIMITY 门洞）：
  gym_door：          (  50,  30, 100, 80)
  study_door：        ( 560,  30, 100, 80)
  office_door：       (  50, 340, 100, 80)

触发区矩形（INTERACT NPC/物件）：
  cyber_minghan：     (320, 185,  80, 80)
  taskboard：         (240, 160,  60, 60)
```

---

## Player 规格（开发参考）

| 属性 | 值 |
|------|-----|
| 占位尺寸 | 24×36px（比精灵帧略小，便于穿过门洞） |
| 移动速度 | 120px/s（内部坐标） |
| 碰撞盒 | 24×30px（底部对齐，头部略小） |
| 占位颜色 | `0x4fc3f7`（亮蓝色） |

**G3/G4 开发顺序说明**：
- G3 创建 WorldScene 时，用 `this.add.circle(360, 280, 12, 0x4fc3f7)` 作为玩家占位显示
- G4 创建 Player 类后，G3 的 WorldScene 更新为 `this.player = new Player(this, 360, 280)`
- 这个替换步骤在 G4 验收标准里，不需要在 G3 阶段解决

---

## 触发区类型

| 类型 | 触发方式 | 行为 |
|------|----------|------|
| **PROXIMITY** | 玩家走入区域自动触发 | 发送 `cyber:door:approach`（门洞进入提示） |
| **INTERACT** | 走入区域后按 **E** | 发送 `cyber:npc:interact` 或 `cyber:object:interact` |

Phase 2 门洞的 PROXIMITY 触发显示「即将开放」文字，不发送 `cyber:door:approach`。

---

## 场景与实体常量名（代码中必须使用以下值）

**场景 key**

| 常量 | 值 |
|------|-----|
| `SCENE_WORLD` | `"WorldScene"` |
| `SCENE_GYM` | `"GymScene"` |
| `SCENE_OFFICE` | `"OfficeScene"` |
| `SCENE_STUDY` | `"StudyScene"` |

**NPC 标识符**

| 常量 | 值 | 所在场景 |
|------|-----|---------|
| `NPC_CYBER` | `"cyber_minghan"` | WorldScene |
| `NPC_HEALTH` | `"health_coach"` | GymScene |

**物件标识符**

| 常量 | 值 | 所在场景 |
|------|-----|---------|
| `OBJ_TASKBOARD` | `"taskboard"` | WorldScene |
| `OBJ_WEIGHT_CAL` | `"weight_calendar"` | GymScene |
| `OBJ_TRAINING_LOG` | `"training_log"` | GymScene |

**触发区 type 值（Tilemap Object Layer 属性）**

| type 值 | 含义 |
|---------|------|
| `"door_to_gym"` | 触发进入健身房提示 |
| `"door_to_office"` | 触发进入办公室提示（Phase 2 门洞） |
| `"door_to_study"` | 触发进入学习室提示（Phase 2 门洞） |
| `"exit_to_world"` | 自动返回主世界 |
| `"spawn"` | 玩家出生点 |

---

## Tilemap 规格

| 参数 | 规格 |
|------|------|
| 图块尺寸 | 16×16 px |
| 格式 | Tiled JSON（`.tmj`）+ PNG Tileset |
| Object Layer 名称 | `"triggers"` |
| 碰撞层名称 | `"collision"` |

Phase 1 先用手写矩形代替 Tilemap，等美术资产交付后替换。

---

## EventBus 实现方式

```javascript
// 发送事件
window.dispatchEvent(new CustomEvent('cyber:事件名', { detail: { /* payload */ } }));

// 监听事件
window.addEventListener('cyber:事件名', (e) => { const payload = e.detail; });
```

所有事件名以 `cyber:` 前缀开头。

---

## EventBus 事件清单

### Phaser → HTML（游戏层发送）

#### `cyber:npc:interact`
玩家在 NPC 的 INTERACT 触发区按 E。

```javascript
{ npcId: "cyber_minghan", npcName: "赛博明翰" }
```

#### `cyber:object:interact`
玩家在物件的 INTERACT 触发区按 E。

```javascript
{ objectId: "taskboard", contextHint: "可选字符串，GymScene 物件使用" }
```

| objectId | contextHint 值 |
|----------|---------------|
| `"weight_calendar"` | `"用户想查看体重趋势"` |
| `"training_log"` | `"用户想回顾训练记录"` |
| `"taskboard"` | 无 |

#### `cyber:door:approach`
玩家走入 Phase 1 门洞 PROXIMITY 区域。

```javascript
{ targetScene: "GymScene", roomName: "健身房", modeDescription: "进入健康管家模式" }
```

#### `cyber:scene:changed`
场景切换完成，新场景 `create()` 结束时发送。

```javascript
{ sceneKey: "WorldScene", roomName: "中央区" }
```

#### `cyber:notification:badge`
场景加载时查询后端通知数量后发送。

```javascript
{ count: 3 }
```

---

### HTML → Phaser（面板层发送，游戏层监听）

#### `cyber:panel:opened`
任何 HTML 面板打开时。Phaser 响应：**禁用玩家键盘输入**。

```javascript
{ panelId: "dialogue" }
```

#### `cyber:panel:closed`
任何 HTML 面板关闭时。Phaser 响应：**重新启用玩家键盘输入**。

```javascript
{ panelId: "dialogue" }
```

#### `cyber:door:confirmed`
用户在入口提示按 Y。Phaser 响应：淡出 → `scene.start(targetScene)`。

```javascript
{ targetScene: "GymScene" }
```

#### `cyber:door:cancelled`
用户在入口提示按 N。payload 为空。Phaser 响应：恢复移动输入。

#### `cyber:review:done`
/review 面板完成全部审批。Phaser 响应：任务板物件清空动效。

```javascript
{ processedCount: 3 }
```

---

## 面板 ID 表

| panelId | 对应面板 |
|---------|---------|
| `"dialogue"` | NPC 对话框 |
| `"room-entry"` | 房间入口确认提示 |
| `"taskboard"` | /review 任务板 |
| `"review"` | /review 审批面板 |
| `"kg"` | /kg 知识图谱 |
| `"prune"` | /prune 老化管理 |

---

## 目录结构

```
frontend/
├── index.html              ← Agent 4 负责
├── client.js               ← Agent 4 负责
├── style/                  ← Agent 4 负责
├── panels/                 ← Agent 4 负责
└── game/                   ← Agent 3 负责
    ├── main.js
    ├── roomConfig.js
    ├── colors.js            ← 颜色常量（0xRRGGBB 格式，不是 CSS 变量）
    ├── scenes/
    │   ├── WorldScene.js
    │   ├── GymScene.js
    │   ├── OfficeScene.js   ← stub
    │   └── StudyScene.js    ← stub
    └── objects/
        ├── Player.js
        └── NPC.js
```

**颜色常量必须用 Phaser 格式（CSS 变量在 Canvas 里无效）：**

```javascript
// frontend/game/colors.js
export const COLORS = {
  BG:       0x0d1117,
  CARD_BG:  0x161b22,
  BORDER:   0x30363d,
  TEXT:     0xc9d1d9,
  ID:       0xe05c5c,
  EGO:      0x3fb950,
  SUPEREGO: 0xf0a500,
};
```

---

## G11 通知查询的离线容错

后端未启动时 fetch 会抛出网络错误，必须捕获否则场景加载失败：

```javascript
// WorldScene.js create() 末尾
async fetchNotifications() {
  try {
    const res = await fetch('/api/notifications');
    if (!res.ok) return;
    const data = await res.json();
    window.dispatchEvent(new CustomEvent('cyber:notification:badge', {
      detail: { count: data.count ?? 0 }
    }));
  } catch (e) {
    // 后端未启动时静默失败，不影响游戏加载
    console.warn('[G11] backend offline, skip notification badge');
  }
}
```

---

## 本地测试命令

```bash
# 前端（frontend/ 目录下）
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
python -m http.server 3000 --directory frontend
# 浏览器打开 http://localhost:3000

# 后端（需要 Agent 4 完成 B6 后才能启动）
uvicorn api.main:app --reload --port 8000
```

测试 EventBus（在浏览器控制台手动触发，不需要等 Agent 4）：

```javascript
// 模拟走近 NPC（测试对话框是否弹出）
window.dispatchEvent(new CustomEvent('cyber:npc:interact', {
  detail: { npcId: 'cyber_minghan', npcName: '赛博明翰' }
}));

// 模拟面板关闭（测试角色是否恢复移动）
window.dispatchEvent(new CustomEvent('cyber:panel:closed', {
  detail: { panelId: 'dialogue' }
}));
```
