# 赛博明翰 · Step 1：AI 概念图生成指南

> 操作者：产品负责人（明翰）  
> 用途：用 AI 生成像素风概念参考图，交给像素艺术家作为临摹蓝图  
> 执行时机：在委托像素艺术家之前完成

---

## 推荐工具：Midjourney

订阅 Standard 及以上档位（支持 `--sref` 风格参考参数）。

## 你需要准备的参考截图（从星露谷游戏内截取）

| 参考图 | 用途 |
|--------|------|
| 角色正面全身截图 | 角色设计风格基准 |
| 室内房间俯视截图 | Tilemap / 房间风格基准 |
| NPC 对话框截图 | 对话框 UI 风格基准 |

## 生成流程

```
1. 在 Midjourney 输入 Prompt
2. 用 --sref [截图链接] 注入星露谷风格
3. 生成 4 张变体，选最符合的 1-2 张
4. 把选中的图发给像素艺术家，作为绘制 Sprite Sheet 的蓝图
```

## 各素材 Prompt 模板

**角色概念图（给像素艺术家临摹用）**
```
pixel art game character, full body, front view, [角色描述],
stardew valley style, 32x48 pixels, sprite reference,
simple design, clean silhouette, dark background
--sref [星露谷角色截图] --sw 150 --style raw
```

**房间背景参考**
```
pixel art interior room, top-down RPG view, [房间描述],
stardew valley aesthetic, cozy indoor scene, dark tone,
wooden floor, 16-bit game background
--sref [星露谷室内截图] --sw 120 --style raw
```

**UI 面板边框**
```
pixel art UI panel border frame, RPG inventory window style,
dark background, pixel perfect edges, stardew valley UI aesthetic,
wooden frame texture, no rounded corners
--sref [星露谷背包界面截图] --sw 100 --style raw
```

## 哪些素材 AI 可直接出图

- 房间背景参考图 → 交给像素艺术家作为 Tilemap 制作蓝图
- UI 面板边框概念图 → 交给前端作为 HTML/CSS 面板皮肤参考

## 哪些素材需要像素艺术家最终制作

- 角色 Sprite Sheet（需逐帧绘制动画，AI 帧间一致性不可靠）
- 可交互物件

> **注意**：不要直接用 AI 输出图作为游戏资产。AI 概念图的作用是给像素艺术家一个清晰的视觉方向，最终交付物仍需手工绘制。
