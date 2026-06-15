import { COLORS } from '../colors.js';
import { Player } from '../objects/Player.js';
import { TriggerSystem } from '../objects/TriggerSystem.js';

export class StudyScene extends Phaser.Scene {
  constructor() { super({ key: 'StudyScene' }); }

  create() {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG);
    gfx.fillRect(0, 0, 720, 450);
    gfx.fillStyle(0x1a1508, 1);  // 暖黄偏橙氛围底色
    gfx.fillRect(20, 20, 680, 410);
    gfx.lineStyle(1, COLORS.SUPEREGO, 0.4);
    gfx.strokeRect(20, 20, 680, 410);

    this.add.text(285, 28, '学习室 / STUDY', {
      fontSize: '9px', color: '#c9d1d9', fontFamily: 'monospace',
    });
    this.add.text(240, 200, '[ Phase 2  建设中 ]', {
      fontSize: '10px', color: '#f0a500', fontFamily: 'monospace',
    });

    gfx.lineStyle(1, COLORS.BORDER, 0.5);
    gfx.strokeRect(300, 400, 120, 38);
    this.add.text(318, 408, '[出口 → 中央区]', {
      fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace',
    });

    this.player = new Player(this, 360, 370);

    this.triggers = new TriggerSystem(this);
    this.triggers.add({
      id: 'exit_world', kind: 'proximity', type: 'exit_to_world',
      rect: new Phaser.Geom.Rectangle(300, 400, 120, 38),
      onTrigger: () => {
        this.cameras.main.fadeOut(300, 0, 0, 0);
        this.cameras.main.once('camerafadeoutcomplete', () => this.scene.start('WorldScene'));
      },
    });

    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
        detail: { sceneKey: 'StudyScene', roomName: '学习室' },
      }));
    });
  }

  update() {
    this.player.update();
    this.triggers.update(this.player.x, this.player.y);
  }
}
