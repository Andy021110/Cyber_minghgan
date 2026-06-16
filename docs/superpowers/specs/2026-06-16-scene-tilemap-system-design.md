# Spec 1: 场景视觉 + Tilemap 系统

**目标：** 把现有的矩形占位符场景替换为基于 Tiled JSON 的多图层地图，实现真正的星露谷风格室内场景，包括相机跟随、Y轴深度排序、NPC 精灵更新。

**技术栈：** Phaser 3 Tilemap API、Tiled 编辑器、Stardew Valley 室内 tileset (spring_indoors.png + Floors.png + furniture.png)

---

## 1. 架构概述

```
Tiled 编辑器 (用户设计)
    ↓ 导出 JSON
public/assets/maps/
    world.json / gym.json / study.json / office.json
    ↓ Phaser.Tilemaps.ParseToTilemap()
BaseIndoorScene (抽象基类)
    ├── 4层渲染：background, floor, objects, foreground
    ├── 相机跟随玩家
    ├── Y轴深度排序 (update loop)
    └── 碰撞物体组 (objects层 + 自定义矩形)
WorldScene / GymScene / StudyScene / OfficeScene
    └── 继承 BaseIndoorScene，各自加载对应地图
```

---

## 2. 地图图层规范（Tiled 里的4个图层）

| 图层名 | 类型 | 用途 | 碰撞 |
|--------|------|------|------|
| `background` | Tile Layer | 墙面、壁纸、踢脚线 | 无 |
| `floor` | Tile Layer | 地板砖 | 无 |
| `objects` | Tile Layer | 家具、书架、设备 | **有**（setCollisionByExclusion） |
| `foreground` | Tile Layer | 前景遮挡（如悬挂物） | 无，但 depth > player |

图层命名必须精确匹配，代码按名称引用。

---

## 3. Tileset 文件清单

| 文件 | 来源 | 用途 |
|------|------|------|
| `spring_indoors.png` | 游戏文件提取 | 室内墙/窗/门框 |
| `Floors.png` | 已有 (`frontend/public/assets/stardew/`) | 地板砖 |
| `furniture.png` | 已有 | 家具、书架、设备 |

Tiled 项目需要引用这三个文件为外部 tileset。Phaser 加载时同样引用。

---

## 4. BaseIndoorScene 设计

### 4.1 Tilemap 加载（create 阶段）

```typescript
// 子类调用：this.loadMap('world', ['spring_indoors', 'floors', 'furniture'])
protected loadMap(key: string, tilesetKeys: string[]) {
  const map = this.make.tilemap({ key });

  // 加载 tileset（PNG key 必须在 preload 里加载）
  const tilesets = tilesetKeys.map(k =>
    map.addTilesetImage(k, k)
  ).filter(Boolean);

  // 按顺序创建图层
  this.bgLayer  = map.createLayer('background', tilesets)!.setDepth(0);
  this.floorLayer = map.createLayer('floor', tilesets)!.setDepth(1);
  this.objLayer = map.createLayer('objects', tilesets)!.setDepth(2);
  this.fgLayer  = map.createLayer('foreground', tilesets)!.setDepth(100);

  // 碰撞：objects 层中非空的 tile 都有碰撞
  this.objLayer.setCollisionByExclusion([-1]);

  // 世界边界 = 地图大小
  this.physics.world.setBounds(0, 0, map.widthInPixels, map.heightInPixels);

  // 相机跟随
  this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
  this.cameras.main.startFollow(this.player, true, 0.1, 0.1);
}
```

### 4.2 Y轴深度排序

```typescript
// update() 里执行：
update() {
  // 玩家
  this.player.setDepth(this.player.y);
  // 所有 NPC
  this.npcs.forEach(npc => npc.setDepth(npc.y));
}
// foreground 层 depth=100 自动遮挡所有 Y < 某阈值的角色
```

### 4.3 玩家与地图碰撞

```typescript
this.physics.add.collider(this.player, this.objLayer);
```

---

## 5. 地图尺寸规范

每个房间在 Tiled 里的设计尺寸：

| 房间 | 宽 × 高 (格数) | Tile 大小 | 实际像素 |
|------|---------------|-----------|---------|
| 中央区 WorldScene | 40 × 28 | 16×16 | 640×448 |
| 健身房 GymScene | 30 × 22 | 16×16 | 480×352 |
| 学习室 StudyScene | 30 × 22 | 16×16 | 480×352 |
| 办公室 OfficeScene | 24 × 18 | 16×16 | 384×288 |

Phaser 渲染时按 2× 缩放（所有 scene 的 scale 配置不变）。

---

## 6. NPC 精灵更新

| NPC | 当前精灵 | 修改为 | 文件 |
|-----|---------|--------|------|
| 赛博明翰（所有场景） | sebastian | sebastian（保持） | Sebastian.png |
| 健康管家（GymScene） | sebastian | abigail | Abigail.png |
| 玩家 | sebastian + 蓝色滤色 | 保持 | - |

GymScene 的 NPC 在 preload 里改加载 `abigail`，create 里修改 spriteKey。

---

## 7. 物品交互框架

房间内可交互物品（任务板、书架、健身器材等）通过 Tiled 的 **Object Layer** 标记位置：

```
Tiled Object Layer: "interactables"
每个 Object 有自定义属性：
  - type: "task_board" | "bookshelf" | "equipment"
  - label: "查看任务" | "检索知识" | ...
  - action: "query_kg" | "open_dialog" | ...
```

Phaser 在 create 里读取这些 Object，生成不可见的碰撞区域，玩家走近时显示交互提示 `[F] 查看`。

---

## 8. 实施分阶段

### 第一阶段（不等游戏文件，现在就做）

- 实现 BaseIndoorScene 类（tilemap 加载、相机、深度排序、碰撞）
- 各场景继承 BaseIndoorScene
- GymScene NPC 换 Abigail
- 物品交互框架（读 Tiled Object Layer）
- **占位地图**：用代码生成简单的 16×16 tile 地图测试流程

### 第二阶段（拿到游戏文件、用 Tiled 设计地图后）

- 导入用户设计的 4 个 .tmj 地图文件
- 配置 spring_indoors.png tileset
- 调整每个房间的碰撞区域
- 添加真实家具位置的交互物品

---

## 9. 不做的事（YAGNI）

- 不做多人同步
- 不做地图编辑器（用 Tiled 就够）
- 不做昼夜变化（现有设计没有）
- 不做随机地图生成
