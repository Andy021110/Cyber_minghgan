import { COLORS } from '../colors.js';
import { Player } from '../objects/Player.js';
import { TriggerSystem } from '../objects/TriggerSystem.js';

export class OfficeScene extends Phaser.Scene {
  constructor() { super({ key: 'OfficeScene' }); }

  create() {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG);
    gfx.fillRect(0, 0, 720, 450);
    gfx.fillStyle(0x1c2333, 1);  // 冷白偏蓝氛围底色
    gfx.fillRect(20, 20, 680, 410);
    gfx.lineStyle(1, COLORS.ID, 0.4);
    gfx.strokeRect(20, 20, 680, 410);

    this.add.text(285, 28, '办公室 / OFFICE', {
      fontSize: '9px', color: '#c9d1d9', fontFamily: 'monospace',
    });
    this.add.text(240, 200, '[ Phase 2  建设中 ]', {
      fontSize: '10px', color: '#e05c5c', fontFamily: 'monospace',
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
        detail: { sceneKey: 'OfficeScene', roomName: '办公室' },
      }));
    });
  }

  update() {
    this.player.update();
    this.triggers.update(this.player.x, this.player.y);
  }
}
