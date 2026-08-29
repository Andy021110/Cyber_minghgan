/**
 * Phaser 侧颜色（必须与 src/styles/tokens.css 的 --game-* 保持一致）。
 *
 * 原为 GitHub Dark 冷灰（0x0d1117 / 0x161b22 / 0x30363d），与 React 面板层的暖棕
 * 羊皮纸色系正面对冲 —— 冷暖同屏是"廉价感"的直接来源。统一为暖色夜景。
 * 改这里时记得同步改 tokens.css，反之亦然。
 */
export const COLORS = {
  BG:       0x241408,
  CARD_BG:  0x33200f,
  BORDER:   0x6b3a10,
  TEXT:     0xf0d090,
  ID:       0xe05c5c,
  EGO:      0x3fb950,
  SUPEREGO: 0xf0a500,
} as const;
