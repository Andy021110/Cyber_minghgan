import Phaser from 'phaser';
import type { TriggerSystem } from './TriggerSystem';

export interface NPCPatrol {
  x1:     number;
  x2:     number;
  speed?: number;  // pixels/sec, default 30
}

export interface NPCOpts {
  npcId:          string;
  npcName:        string;
  spriteKey:      string;
  x:              number;
  y:              number;
  patrol?:        NPCPatrol;
  triggerSystem?: TriggerSystem;
}

export class NPC {
  readonly npcId:   string;
  readonly npcName: string;
  private sprite:   Phaser.GameObjects.Sprite;
  private label:    Phaser.GameObjects.Text;

  private patrol:   NPCPatrol | null = null;
  private dir:      1 | -1 = 1;
  private curAnim:  string = '';

  constructor(scene: Phaser.Scene, opts: NPCOpts) {
    const { npcId, npcName, spriteKey, x, y, patrol, triggerSystem } = opts;
    this.npcId   = npcId;
    this.npcName = npcName;

    this.sprite = scene.add.sprite(x, y, spriteKey);
    this.sprite.setScale(2);
    this.sprite.setDepth(10);

    // Register animations (idempotent)
    const anims = scene.anims;
    const reg = (key: string, start: number, end: number, fps: number) => {
      if (!anims.exists(key))
        anims.create({ key, frames: anims.generateFrameNumbers(spriteKey, { start, end }), frameRate: fps, repeat: -1 });
    };
    reg(`${spriteKey}_idle`,       0,  3, 4);
    reg(`${spriteKey}_walk_right`,  4,  7, 8);
    reg(`${spriteKey}_walk_left`,  12, 15, 8);

    this._play(`${spriteKey}_idle`);

    this.label = scene.add.text(x, y - 28, npcName, {
      fontSize: '6px', color: '#f0d090', fontFamily: 'monospace',
    }).setOrigin(0.5).setDepth(11);

    if (patrol) {
      this.patrol = patrol;
      this.dir    = 1;
    }

    if (triggerSystem) {
      triggerSystem.add({
        id: `npc_${npcId}`, kind: 'interact', type: 'npc',
        rect: new Phaser.Geom.Rectangle(x - 24, y - 26, 48, 52),
        npcId, npcName,
      });
    }
  }

  update(dt: number): void {
    if (!this.patrol) return;
    const { x1, x2, speed = 30 } = this.patrol;
    const dx = speed * (dt / 1000) * this.dir;
    const nx = this.sprite.x + dx;

    if (nx >= x2) { this.sprite.x = x2; this.dir = -1; }
    else if (nx <= x1) { this.sprite.x = x1; this.dir = 1; }
    else { this.sprite.x = nx; }

    const key = this.dir === 1
      ? `${this.sprite.texture.key}_walk_right`
      : `${this.sprite.texture.key}_walk_left`;
    this._play(key);

    this.label.x = this.sprite.x;
  }

  private _play(key: string): void {
    if (this.curAnim !== key) {
      this.curAnim = key;
      this.sprite.play(key);
    }
  }

  destroy(): void {
    this.sprite.destroy();
    this.label.destroy();
  }
}
