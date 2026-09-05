"""
scripts/mascot_cut.py — 三视图立绘 → 桌宠透明素材

输入：frontend/public/assets/mascot/source_three_view.jpg（白底三视图）
输出：frontend/public/assets/mascot/{front,side,back}.png（透明底，裁到角色边界）

为什么用 flood fill 而不是全局色键：
卫衣上的「HKU」白字、鞋的白边、眼白都是白色。全局把白色抠掉会把它们一起打穿。
flood fill 从图像边缘往里填充，只有**与外部连通**的白底会被抠掉，
角色内部的白色完好保留。

JPG 有压缩噪声，纯白不是 (255,255,255) 而是 240~254 抖动，所以阈值用 232 并
配合「与已确认背景相邻」的连通条件，双重保险。
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

SRC = Path("frontend/public/assets/mascot/source_three_view.jpg")
OUT_DIR = Path("frontend/public/assets/mascot")
NAMES = ["front", "side", "back"]
THRESHOLD = 232          # RGB 均值高于此视为"接近白"
PADDING = 12             # 裁剪时给角色留的边距


def flood_fill_background(im: Image.Image) -> Image.Image:
    """从四条边出发，把与边缘连通的近白区域抠成透明。"""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()

    def is_bglike(x: int, y: int) -> bool:
        r, g, b, _ = px[x, y]
        return (r + g + b) / 3 >= THRESHOLD

    seen = [[False] * h for _ in range(w)]
    q: deque[tuple[int, int]] = deque()

    # 种子：四条边上所有近白像素
    for x in range(w):
        for y in (0, h - 1):
            if is_bglike(x, y) and not seen[x][y]:
                seen[x][y] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bglike(x, y) and not seen[x][y]:
                seen[x][y] = True
                q.append((x, y))

    while q:
        x, y = q.popleft()
        px[x, y] = (255, 255, 255, 0)
        for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[nx][ny] and is_bglike(nx, ny):
                seen[nx][ny] = True
                q.append((nx, ny))
    return im


def crop_to_content(im: Image.Image) -> Image.Image:
    """裁到非透明像素的包围盒，四周留 PADDING。"""
    bbox = im.getbbox()          # 基于 alpha 通道
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - PADDING)
    t = max(0, t - PADDING)
    r = min(im.width, r + PADDING)
    b = min(im.height, b + PADDING)
    return im.crop((l, t, r, b))


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"找不到源图：{SRC}")
    im = Image.open(SRC)
    print(f"源图 {im.size}")

    cleared = flood_fill_background(im)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    third = cleared.width // 3
    for i, name in enumerate(NAMES):
        part = cleared.crop((i * third, 0, (i + 1) * third, cleared.height))
        part = crop_to_content(part)
        out = OUT_DIR / f"{name}.png"
        part.save(out)
        print(f"  {name:<6} {part.size}  → {out}")


if __name__ == "__main__":
    main()
