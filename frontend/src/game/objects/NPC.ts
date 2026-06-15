import Phaser from 'phaser';
import type { TriggerSystem } from './TriggerSystem';

export interface NPCOpts {
  npcId:          string;
  npcName:        string;
  spriteKey:      string;
  x:              number;
  y:              number;
  triggerSystem?: TriggerSystem;
}

export class NPC {
  readonly npcId:   string;
  readonly npcName: string;
  private sprite:   Phaser.GameObjects.Sprite;
  private label:    Phaser.GameObjects.Text;

  constructor(scene: Phaser.Scene, opts: NPCOpts) {
    const { npcId, npcName, spriteKey, x, y, triggerSystem } = opts;
    this.npcId   = npcId;
    this.npcName = npcName;

    this.sprite = scene.add.sprite(x, y, spriteKey);
    this.sprite.setScale(2);
    this.sprite.setDepth(10);

    // Create idle animation (idempotent)
    const animKey = `${spriteKey}_idle`;
    if (!scene.anims.exists(animKey)) {
      scene.anims.create({
        key: animKey,
        frames: scene.anims.generateFrameNumbers(spriteKey, { start: 0, end: 3 }),
        frameRate: 4,
        repeat: -1,
      });
    }
    this.sprite.play(animKey);

    this.label = scene.add.text(x, y - 28, npcName, {
      fontSize: '6px', color: '#f0d090', fontFamily: 'monospace',
    }).setOrigin(0.5).setDepth(11);

    if (triggerSystem) {
      triggerSystem.add({
        id: `npc_${npcId}`, kind: 'interact', type: 'npc',
        rect: new Phaser.Geom.Rectangle(x - 24, y - 26, 48, 52),
        npcId, npcName,
      });
    }
  }

  destroy(): void {
    this.sprite.destroy();
    this.label.destroy();
  }
}
