# 你需要做什么 · 个人行动指南

**这份指南只关于你自己需要做的事。代码部分我来负责。**

---

## 你的角色

你是**地图创作者**。Tiled 是你的画笔，我负责让 Phaser 读懂你画的地图。没有你设计的地图，代码框架再完整也是空架子。

---

## 第一步：找到游戏文件（30 分钟）

你需要从星露谷游戏里提取室内 tileset 图片。

**目的：** 这些图片是画房间墙壁、窗户、门框所必需的资源，游戏里的每一个室内场景都用同一张 `spring_indoors.png`。

**操作：**

```bash
# 在终端运行，找到游戏目录：
ls ~/Library/Application\ Support/Steam/steamapps/common/Stardew\ Valley/Content/Maps/
```

找到这几个文件：

| 文件名 | 用途 |
|--------|------|
| `spring_indoors.png` | 室内墙面、窗户、门框、壁纸纹理 |
| `spring_outdoorsTileSheet.png` | 备用，户外地面（可选） |

**找到后，** 把它们复制到：
```
frontend/public/assets/stardew/
```

如果路径不存在或文件名不一样，截个图给我，我帮你确认。

---

## 第二步：下载 Tiled 编辑器（10 分钟）

**下载：** https://www.mapeditor.org/

免费，直接装。Mac 版本下载后拖进 Applications 就行。

**目的：** Tiled 是业界标准的 2D 地图编辑器，星露谷本身就用 Tiled 设计地图。你用它来「画」每个房间的布局，然后导出 JSON，我的代码会读取这个 JSON 来渲染场景。

---

## 第三步：看一个教程（20–30 分钟）

**YouTube 搜索：** `Tiled map editor tutorial beginner`

推荐选 10–15 分钟以内的视频，内容要覆盖：

| 你需要学会 | 不需要学 |
|-----------|---------|
| ✅ 新建地图、设置格子大小 | ❌ 动画 Tile |
| ✅ 加载 tileset（图片） | ❌ 自定义脚本 |
| ✅ 用画笔在图层上涂格子 | ❌ Infinite Map 模式 |
| ✅ 添加多个图层、命名图层 | ❌ Terrain（地形刷） |
| ✅ 导出为 JSON（.tmj 格式） | |

**看完后你应该能：** 打开 Tiled，新建一个 30×20 的地图，加载一张图片作为 tileset，在图层上涂几个格子，然后 File → Export As → JSON 保存。

---

## 第四步：设计三个房间（2–4 小时，可拆开来做）

每个房间都需要 4 个命名精确的图层：

```
background   ← 墙面、壁纸（不可穿越区域的纯装饰）
floor        ← 地板铺满整个房间
objects      ← 家具、书架、设备（这层有碰撞，玩家不能穿过）
foreground   ← 悬挂的东西（如天花板灯，选做）
```

### 中央区（最重要，先做这个）

**大小：** 40 × 28 格

**你需要放的内容：**
- 四周是墙壁（用 `spring_indoors.png` 里的墙面格子）
- 地板铺满（用 `Floors.png` 第一行的木地板格子）
- 左上角区域：GYM 入口（一个门洞）
- 右上角区域：STUDY 入口（一个门洞）
- 中间：一张桌子 + 任务板（用 `furniture.png`）
- 大概位置留出来给 NPC 站立即可（不需要精确）

### 健身房

**大小：** 30 × 22 格

**内容：** 健身器材几件（furniture.png 里有）、出口门洞

### 学习室

**大小：** 30 × 22 格

**内容：** 书桌、书架（furniture.png 里有）、出口门洞

---

## 第五步：导出并交给我

每个房间设计好后，在 Tiled 里：

1. `File → Export As`
2. 格式选 **JSON map files (*.tmj)**（也就是 `.json` 后缀）
3. 保存到：

```
frontend/public/assets/maps/world.json
frontend/public/assets/maps/gym.json
frontend/public/assets/maps/study.json
```

然后告诉我文件放好了，我来写加载代码。

---

## 时间预期

| 任务 | 时间 |
|------|------|
| 找游戏文件 | 15–30 分钟 |
| 装 Tiled | 10 分钟 |
| 看教程 | 20–30 分钟 |
| 设计中央区 | 60–90 分钟 |
| 设计健身房 + 学习室 | 各 30–60 分钟 |

**中央区先做。** 其他的可以之后补。

---

## 如果遇到问题

- **找不到游戏文件**：截图给我，可能 Steam 目录结构不一样
- **Tiled 不知道怎么加载 tileset**：截图给我，我一步步说
- **不知道 furniture.png 里某个格子是什么**：截图框选给我，我帮你识别
- **导出 JSON 报错**：把错误信息粘贴给我

你不需要完美，只需要「说得过去」就行。我后面可以帮你调整。
