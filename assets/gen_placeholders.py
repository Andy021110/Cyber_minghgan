"""
生成开发占位图资产。
运行：python3 assets/gen_placeholders.py
"""
from PIL import Image, ImageDraw
import os

OUT = os.path.dirname(os.path.abspath(__file__))

# ── 精灵表规格 ──────────────────────────────────────────────
# 每帧 32×48px，4 列 × 6 行 = 128×288px
FRAME_W, FRAME_H = 32, 48
COLS, ROWS = 4, 6
SHEET_W, SHEET_H = FRAME_W * COLS, FRAME_H * ROWS

ROW_LABELS = ["idle", "walk_dn", "walk_up", "walk_lt", "walk_rt", "interact"]

def make_sprite_sheet(filename, body_color, outline_color, label):
    """生成一张带行标签的精灵表占位图。"""
    img = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for row in range(ROWS):
        for col in range(COLS):
            x0 = col * FRAME_W
            y0 = row * FRAME_H
            x1 = x0 + FRAME_W - 1
            y1 = y0 + FRAME_H - 1

            # 帧背景（透明度随列变化，区分帧序）
            alpha = 180 - col * 20
            r, g, b = body_color
            draw.rectangle([x0, y0, x1, y1], fill=(r, g, b, alpha))
            draw.rectangle([x0, y0, x1, y1], outline=outline_color + (255,), width=1)

            # 简单「人形」：头圆 + 身体矩形
            cx = x0 + FRAME_W // 2
            head_r = 7
            draw.ellipse(
                [cx - head_r, y0 + 4, cx + head_r, y0 + 4 + head_r * 2],
                fill=(220, 220, 220, 230),
            )
            body_top = y0 + 4 + head_r * 2 + 2
            draw.rectangle(
                [cx - 7, body_top, cx + 7, y0 + FRAME_H - 8],
                fill=(200, 200, 200, 200),
            )

            # 行号标注（左上角小字）
            draw.text((x0 + 2, y0 + 2), ROW_LABELS[row][:3], fill=(255, 255, 100, 220))
            draw.text((x0 + 2, y0 + 12), f"f{col}", fill=(255, 255, 255, 180))

    # 右下角打标签
    draw.text((2, SHEET_H - 12), label, fill=(255, 255, 0, 200))

    path = os.path.join(OUT, filename)
    img.save(path)
    print(f"  ✅ {filename}  ({SHEET_W}×{SHEET_H}px)")


# ── 物件图规格 ──────────────────────────────────────────────
def make_object(filename, bg_color, border_color, icon_char, size=(32, 48)):
    """生成可交互物件占位图（带 normal/active 两种状态）。"""
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = bg_color
    draw.rectangle([0, 0, w - 1, h - 1], fill=(r, g, b, 200))
    draw.rectangle([0, 0, w - 1, h - 1], outline=border_color + (255,), width=2)
    # 图标字符居中
    draw.text((w // 2 - 5, h // 2 - 7), icon_char, fill=(255, 255, 255, 240))
    path = os.path.join(OUT, filename)
    img.save(path)
    print(f"  ✅ {filename}  ({w}×{h}px)")


# ── 简易 Tileset 占位 ───────────────────────────────────────
def make_tileset(filename):
    """生成 8×8 张 16×16 Tile 的简易 Tileset（128×128px）。"""
    TILE = 16
    COLS_T, ROWS_T = 8, 8
    img = Image.new("RGBA", (TILE * COLS_T, TILE * ROWS_T), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    palette = [
        (13, 17, 23),    # 0 黑底（透明）
        (22, 27, 34),    # 1 深灰地板
        (30, 40, 55),    # 2 中灰地板
        (48, 54, 61),    # 3 浅灰墙壁
        (63, 185, 80),   # 4 绿色草地
        (240, 165, 0),   # 5 橙色地毯
        (224, 92, 92),   # 6 红色装饰
        (100, 120, 180), # 7 蓝色门框
    ]

    for row in range(ROWS_T):
        for col in range(COLS_T):
            idx = (row * COLS_T + col) % len(palette)
            color = palette[idx] + (220,)
            x0, y0 = col * TILE, row * TILE
            draw.rectangle([x0, y0, x0 + TILE - 1, y0 + TILE - 1], fill=color)
            draw.rectangle([x0, y0, x0 + TILE - 1, y0 + TILE - 1],
                           outline=(80, 80, 80, 180), width=1)
            # Tile 编号
            draw.text((x0 + 2, y0 + 4), str(row * COLS_T + col), fill=(200, 200, 200, 160))

    path = os.path.join(OUT, filename)
    img.save(path)
    print(f"  ✅ {filename}  (128×128px, 64 tiles 16×16)")


# ── 主程序 ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n生成占位图资产...\n")

    print("【精灵表】")
    make_sprite_sheet("player.png",        (79, 195, 247), (30, 136, 229),  "PLAYER")
    make_sprite_sheet("npc_cyber_v1.png",  (126, 87, 194), (94, 53, 177),   "CYBER_v1")
    make_sprite_sheet("npc_cyber_v2.png",  (77, 208, 225), (0, 172, 193),   "CYBER_v2")
    make_sprite_sheet("npc_cyber_v3.png",  (255, 167, 38), (245, 124, 0),   "CYBER_v3")
    make_sprite_sheet("npc_health.png",    (102, 187, 106),(56, 142, 60),   "HEALTH")

    print("\n【可交互物件】")
    make_object("obj-taskboard-normal.png", (30, 40, 55),  (80, 100, 130), "TB")
    make_object("obj-taskboard-active.png", (30, 55, 40),  (63, 185, 80),  "TB!")
    make_object("obj-weight-calendar-normal.png", (40, 30, 55), (100, 80, 160), "WC")
    make_object("obj-weight-calendar-active.png", (55, 30, 55), (185, 63, 185), "WC!")
    make_object("obj-training-log-normal.png",    (40, 45, 30), (100, 140, 60),  "TL")
    make_object("obj-training-log-active.png",    (40, 60, 30), (80,  200, 80),  "TL!")

    print("\n【Tileset】")
    make_tileset("tileset-placeholder.png")

    print("\n✅ 所有占位图已生成到 assets/ 目录\n")
    print("说明：")
    print("  精灵表格式：128×288px（32×48px × 4列6行）")
    print("  行顺序：idle / walk_dn / walk_up / walk_lt / walk_rt / interact")
    print("  Agent 2 交付真实资产后，直接替换同名文件即可\n")
