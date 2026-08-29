#!/usr/bin/env python3
"""Generate two map options from Stardew Valley TMX files.

Option A: SamHouse.tmx → Phaser-compatible JSON (single house, 25×25)
Option B: SamHouse + JoshHouse side-by-side → Tiled TMX preview + Phaser JSON (50×25)

GID remapping note:
  SamHouse:  townInterior(1-2176) | townInterior_2(2177-3488) | paths(3489-3552)
  JoshHouse: townInterior(1-2176) | paths(2177-2240)          | townInterior_2(2241-3552)
  → JoshHouse tiles are remapped to SamHouse's canonical GID space before merging.
"""

import xml.etree.ElementTree as ET
import json
import os
import shutil

MAPS_SRC   = "/Users/minghan/Desktop/知识蒸馏/元宝-明翰/星露谷美术资源/Content (unpacked)/Maps"
DEST_DIR   = "/Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend/public/assets/maps"
PREVIEW_DIR = "/Users/minghan/Desktop/知识蒸馏/元宝-明翰/map_previews"

os.makedirs(DEST_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_csv_layer(text):
    vals = []
    for line in text.strip().splitlines():
        for v in line.split(','):
            v = v.strip()
            if v:
                vals.append(int(v))
    return vals

def to_grid(flat, w, h):
    return [flat[r*w:(r+1)*w] for r in range(h)]

def to_flat(grid):
    return [v for row in grid for v in row]

def empty_grid(w, h):
    return [[0]*w for _ in range(h)]

def load_tmx_layers(path):
    """Returns (width, height, {name: 2D grid})."""
    root = ET.parse(path).getroot()
    w = int(root.get('width'))
    h = int(root.get('height'))
    layers = {}
    for layer in root.findall('layer'):
        data = layer.find('data')
        if data is not None and data.get('encoding') == 'csv':
            layers[layer.get('name')] = to_grid(parse_csv_layer(data.text), w, h)
    return w, h, layers


# ── GID remapping ─────────────────────────────────────────────────────────────

def remap_josh(gid):
    """Remap a JoshHouse GID to SamHouse canonical GID space."""
    if gid == 0:
        return 0
    if gid <= 2176:       # townInterior — same in both
        return gid
    if gid <= 2240:       # paths in Josh (firstgid=2177, 64 tiles) → paths in Sam (firstgid=3489)
        return 3489 + (gid - 2177)
    # townInterior_2 in Josh (firstgid=2241) → townInterior_2 in Sam (firstgid=2177)
    return 2177 + (gid - 2241)

def remap_grid(grid, fn):
    return [[fn(v) for v in row] for row in grid]


# ── Canonical tileset descriptors (SamHouse order) ───────────────────────────

SAM_TILESETS = [
    {"firstgid": 1,    "name": "townInterior",   "image": "townInterior.png",
     "imagewidth": 512, "imageheight": 1088, "tilewidth": 16, "tileheight": 16,
     "columns": 32, "tilecount": 2176, "margin": 0, "spacing": 0},
    {"firstgid": 2177, "name": "townInterior_2", "image": "townInterior_2.png",
     "imagewidth": 512, "imageheight": 656,  "tilewidth": 16, "tileheight": 16,
     "columns": 32, "tilecount": 1312, "margin": 0, "spacing": 0},
    {"firstgid": 3489, "name": "paths",          "image": "paths.png",
     "imagewidth": 64,  "imageheight": 256,  "tilewidth": 16, "tileheight": 16,
     "columns": 4,  "tilecount": 64,   "margin": 0, "spacing": 0},
]

SAM_LAYER_ORDER = ["Back", "Back2", "Buildings", "Front", "Front2",
                   "AlwaysFront", "AlwaysFront2", "Paths"]


# ── Phaser JSON builder ───────────────────────────────────────────────────────

def make_phaser_json(width, height, layers_dict, layer_order, tilesets):
    layers = []
    for i, name in enumerate(layer_order):
        grid = layers_dict.get(name, empty_grid(width, height))
        layers.append({
            "id": i + 1, "name": name, "type": "tilelayer",
            "width": width, "height": height, "x": 0, "y": 0,
            "opacity": 1, "visible": True,
            "data": to_flat(grid),
        })
    return {
        "version": "1.10", "tiledversion": "1.12.2",
        "orientation": "orthogonal", "renderorder": "right-down",
        "width": width, "height": height,
        "tilewidth": 16, "tileheight": 16,
        "infinite": False,
        "nextlayerid": len(layers) + 1, "nextobjectid": 1,
        "tilesets": tilesets,
        "layers": layers,
    }


# ── TMX writer (for Tiled preview) ────────────────────────────────────────────

def write_merged_tmx(path, w, h, layers_dict, layer_order):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<map version="1.10" tiledversion="1.12.2" orientation="orthogonal" '
        f'renderorder="right-down" compressionlevel="0" '
        f'width="{w}" height="{h}" tilewidth="16" tileheight="16" '
        f'infinite="0" nextlayerid="{len(layer_order)+1}" nextobjectid="1">',
        ' <tileset firstgid="1" name="1" tilewidth="16" tileheight="16" tilecount="2176" columns="32">',
        '  <image source="townInterior.png" width="512" height="1088"/>',
        ' </tileset>',
        ' <tileset firstgid="2177" name="2" tilewidth="16" tileheight="16" tilecount="1312" columns="32">',
        '  <image source="townInterior_2.png" width="512" height="656"/>',
        ' </tileset>',
        ' <tileset firstgid="3489" name="p" tilewidth="16" tileheight="16" tilecount="64" columns="4">',
        '  <image source="paths.png" width="64" height="256"/>',
        ' </tileset>',
    ]
    for i, name in enumerate(layer_order):
        grid = layers_dict.get(name, empty_grid(w, h))
        lines.append(f' <layer id="{i+1}" name="{name}" width="{w}" height="{h}">')
        lines.append('  <data encoding="csv">')
        for r, row in enumerate(grid):
            suffix = ',' if r < h - 1 else ''
            lines.append(','.join(str(v) for v in row) + suffix)
        lines.append('  </data>')
        lines.append(' </layer>')
    lines.append('</map>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


# ── Main ──────────────────────────────────────────────────────────────────────

# Load source maps
sam_w, sam_h, sam_layers = load_tmx_layers(os.path.join(MAPS_SRC, "SamHouse.tmx"))
josh_w, josh_h, josh_layers_raw = load_tmx_layers(os.path.join(MAPS_SRC, "JoshHouse.tmx"))

# Remap JoshHouse GIDs to SamHouse canonical space
josh_layers = {name: remap_grid(grid, remap_josh) for name, grid in josh_layers_raw.items()}

print(f"SamHouse:  {sam_w}×{sam_h}, layers: {list(sam_layers.keys())}")
print(f"JoshHouse: {josh_w}×{josh_h}, layers: {list(josh_layers.keys())}")

# ── Option A: SamHouse single house ──────────────────────────────────────────
option_a = make_phaser_json(sam_w, sam_h, sam_layers, SAM_LAYER_ORDER, SAM_TILESETS)
out_a = os.path.join(DEST_DIR, "option_a_samhouse.json")
with open(out_a, 'w') as f:
    json.dump(option_a, f, separators=(',', ':'))
print(f"\n✓ Option A → {out_a}  ({sam_w}×{sam_h} tiles, {os.path.getsize(out_a)//1024}KB)")

# ── Option B: SamHouse + JoshHouse merged ─────────────────────────────────────
merged_w = sam_w + josh_w   # 50
merged_h = max(sam_h, josh_h)  # 25

# Canonical layer order: SamHouse layers first, then Josh-only layers
josh_only = [n for n in josh_layers if n not in SAM_LAYER_ORDER]
canonical = SAM_LAYER_ORDER + josh_only

merged_layers = {}
for name in canonical:
    sg = sam_layers.get(name, empty_grid(sam_w, merged_h))
    jg = josh_layers.get(name, empty_grid(josh_w, merged_h))
    # Pad height if needed
    while len(sg) < merged_h: sg.append([0] * sam_w)
    while len(jg) < merged_h: jg.append([0] * josh_w)
    merged_layers[name] = [sr + jr for sr, jr in zip(sg, jg)]

# Phaser JSON
option_b = make_phaser_json(merged_w, merged_h, merged_layers, canonical, SAM_TILESETS)
out_b = os.path.join(DEST_DIR, "option_b_merged.json")
with open(out_b, 'w') as f:
    json.dump(option_b, f, separators=(',', ':'))
print(f"✓ Option B Phaser JSON → {out_b}  ({merged_w}×{merged_h} tiles, {os.path.getsize(out_b)//1024}KB)")

# Tiled TMX for visual preview
tmx_path = os.path.join(PREVIEW_DIR, "merged_sam_josh.tmx")
write_merged_tmx(tmx_path, merged_w, merged_h, merged_layers, canonical)
print(f"✓ Option B Tiled TMX  → {tmx_path}")

# ── Copy tileset PNGs ─────────────────────────────────────────────────────────
for ts in ["townInterior", "townInterior_2", "paths"]:
    src = os.path.join(MAPS_SRC, f"{ts}.png")
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(DEST_DIR, f"{ts}.png"))
        shutil.copy2(src, os.path.join(PREVIEW_DIR, f"{ts}.png"))
        print(f"✓ Copied {ts}.png → DEST_DIR + PREVIEW_DIR")
    else:
        print(f"✗ Missing: {src}")

# ── Option C: JoshHouse only (GIDs remapped to SamHouse canonical space) ──────
JOSH_LAYER_ORDER = ["Back", "Back2", "Buildings", "Front", "Front2", "Front3", "Paths"]
option_c = make_phaser_json(josh_w, josh_h, josh_layers, JOSH_LAYER_ORDER, SAM_TILESETS)
out_c = os.path.join(DEST_DIR, "option_c_joshhouse.json")
with open(out_c, 'w') as f:
    json.dump(option_c, f, separators=(',', ':'))
print(f"✓ Option C (JoshHouse) → {out_c}  ({josh_w}×{josh_h} tiles, {os.path.getsize(out_c)//1024}KB)")

print("\nDone.")
print(f"  Open in Tiled:  {tmx_path}")
print(f"  Phaser assets:  {DEST_DIR}/")
