import { COLORS } from '../colors.js';

// 占位阶段：颜色矩形 + alpha 脉冲代替 Sprite Sheet 帧动画（G12 替换）
export class NPC {
  /**
   * @param {Phaser.Scene} scene
   * @param {{ npcId, npcName, spriteKey, x, y, triggerSystem }} opts
   */
  constructor(scene, { npcId, npcName, spriteKey, x, y, triggerSystem }) {
    this.npcId   = npcId;
    this.npcName = npcName;
    this.scene   = scene;

    // 占位矩形
    this.sprite = scene.add.rectangle(x, y, 16, 24, COLORS.ID);

    // 名称标签
    this.label = scene.add.text(x, y - 18, npcName, {
      fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace',
    }).setOrigin(0.5);

    // idle 占位动画：alpha 缓慢脉冲，8fps 近似
    scene.tweens.add({
      targets: this.sprite,
      alpha: { from: 0.65, to: 1 },
      duration: 750,
      yoyo: true,
      repeat: -1,
      ease: 'Linear',
    });

    // 向场景的 TriggerSystem 注册 INTERACT 区（48×52 以 NPC 为中心）
    if (triggerSystem) {
      triggerSystem.add({
        id:      `npc_${npcId}`,
        kind:    'interact',
        type:    'npc',
        rect:    new Phaser.Geom.Rectangle(x - 24, y - 26, 48, 52),
        npcId,
        npcName,
      });
    }
  }

  destroy() {
    this.sprite.destroy();
    this.label.destroy();
  }
}
