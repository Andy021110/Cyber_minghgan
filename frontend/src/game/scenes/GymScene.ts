import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { NPC } from '../objects/NPC';
import { TriggerSystem } from '../objects/TriggerSystem';
import { listen } from '../../eventbus';

const SPAWN_X = 360;
const SPAWN_Y = 380;

export class GymScene extends Phaser.Scene {
  private player!:       Player;
  private triggers!:     TriggerSystem;
  private transitioning  = false;
  private offListeners:  Array<() => void> = [];

  constructor() { super({ key: 'GymScene' }); }

  preload(): void {
    this.load.spritesheet('alex', '/assets/alex.png', { frameWidth: 16, frameHeight: 32 });
    this.load.spritesheet('kent', '/assets/kent.png', { frameWidth: 16, frameHeight: 32 });
    this.load.image('floors', '/assets/stardew/Floors.png');
  }

  create(): void {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG);    gfx.fillRect(0, 0, 720, 450);
    gfx.fillStyle(0x1a2a1a);     gfx.fillRect(40, 40, 640, 380);
    gfx.lineStyle(2, COLORS.EGO, 0.6); gfx.strokeRect(40, 40, 640, 380);
    this.add.tileSprite(360, 230, 640, 380, 'floors').setDepth(0).setAlpha(0.45);

    this.add.text(300, 50, '🏋️ 健身房', { fontSize: '10px', color: '#c9d1d9', fontFamily: 'monospace' });

    // Weight calendar object placeholder
    this.add.rectangle(180, 200, 48, 40, COLORS.EGO, 0.5);
    this.add.text(155, 225, '[体重日历]', { fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace' });

    // Training log object placeholder
    this.add.rectangle(320, 200, 16, 32, COLORS.EGO, 0.4);
    this.add.text(307, 225, '[训练本]', { fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace' });

    // Exit indicator
    this.add.rectangle(360, 420, 48, 12, COLORS.EGO, 0.7);
    this.add.text(340, 426, '[← 出口]', { fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace' });

    this.player   = new Player(this, SPAWN_X, SPAWN_Y);
    this.triggers = new TriggerSystem(this);
    const R = Phaser.Geom.Rectangle;

    new NPC(this, {
      npcId: 'health_coach', npcName: '健康管家',
      spriteKey: 'alex', x: 500, y: 200,
      triggerSystem: this.triggers,
    });

    this.triggers
      .add({ id: 'weight_cal',   kind: 'interact', type: 'object',
             rect: new R(158, 178, 52, 48),
             objectId: 'weight_calendar', contextHint: '用户想查看体重趋势' })
      .add({ id: 'training_log', kind: 'interact', type: 'object',
             rect: new R(308, 182, 28, 48),
             objectId: 'training_log', contextHint: '用户想回顾训练记录' })
      .add({ id: 'exit_to_world', kind: 'proximity', type: 'exit',
             rect: new R(336, 412, 64, 24),
             onTrigger: () => { this.exitToWorld(); } });

    this.offListeners = [
      listen('cyber:panel:opened', () => this.player.disableInput()),
      listen('cyber:panel:closed', () => { if (!this.transitioning) this.player.enableInput(); }),
    ];
    this.events.on('shutdown', () => { this.offListeners.forEach(off => off()); }, this);

    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
        detail: { sceneKey: 'GymScene', roomName: '健身房' },
      }));
    });
  }

  update(): void {
    this.player.update();
    this.triggers.update(this.player.x, this.player.y);
  }

  private exitToWorld(): void {
    if (this.transitioning) return;
    this.transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.transitioning = false;
      this.scene.start('WorldScene');
    });
  }
}
