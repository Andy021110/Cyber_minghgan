import Phaser from 'phaser';
import { COLORS } from '../colors';
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
  private sprite:   Phaser.GameObjects.Rectangle;
  private label:    Phaser.GameObjects.Text;

  constructor(scene: Phaser.Scene, opts: NPCOpts) {
    const { npcId, npcName, x, y, triggerSystem } = opts;
    this.npcId   = npcId;
    this.npcName = npcName;

    this.sprite = scene.add.rectangle(x, y, 16, 24, COLORS.ID);
    this.label  = scene.add.text(x, y - 18, npcName, {
      fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace',
    }).setOrigin(0.5);

    scene.tweens.add({
      targets: this.sprite, alpha: { from: 0.65, to: 1 },
      duration: 750, yoyo: true, repeat: -1, ease: 'Linear',
    });

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
