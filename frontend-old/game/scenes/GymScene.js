import { COLORS } from '../colors.js';
import { Player } from '../objects/Player.js';
import { TriggerSystem } from '../objects/TriggerSystem.js';
import { NPC } from '../objects/NPC.js';

export class GymScene extends Phaser.Scene {
  constructor() { super({ key: 'GymScene' }); }

  create() {
    this._drawLayout();
    this.player = new Player(this, 360, 375);
    this._setupTriggers();

    // 健康管家 NPC（自动向 this.triggers 注册 INTERACT 区）
    this.npcHealth = new NPC(this, {
      npcId: 'health_coach', npcName: '健康管家',
      spriteKey: 'npc_health',
      x: 360, y: 195,
      triggerSystem: this.triggers,
    });

    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => this._dispatchSceneChanged());
  }

  update() {
    this.player.update();
    this.triggers.update(this.player.x, this.player.y);
  }

  _drawLayout() {
    const gfx = this.add.graphics();

    gfx.fillStyle(COLORS.BG);
    gfx.fillRect(0, 0, 720, 450);
    gfx.fillStyle(COLORS.EGO, 0.05);
    gfx.fillRect(0, 0, 720, 450);

    // 房间边框
    gfx.lineStyle(1, COLORS.EGO, 0.4);
    gfx.strokeRect(20, 20, 680, 410);

    this.add.text(295, 28, '健身房 / GYM', {
      fontSize: '9px', color: '#c9d1d9', fontFamily: 'monospace',
    });

    // 体重日历占位（SUPEREGO 橙色，左侧）
    gfx.fillStyle(COLORS.SUPEREGO, 0.3);
    gfx.fillRect(164, 164, 32, 32);
    gfx.lineStyle(1, COLORS.SUPEREGO, 0.9);
    gfx.strokeRect(164, 164, 32, 32);
    this.add.text(156, 200, '体重日历', {
      fontSize: '6px', color: '#f0a500', fontFamily: 'monospace',
    });

    // 训练记录本占位（BORDER 灰色，右侧）
    gfx.fillStyle(COLORS.BORDER, 0.6);
    gfx.fillRect(524, 156, 16, 40);
    gfx.lineStyle(1, COLORS.TEXT, 0.6);
    gfx.strokeRect(524, 156, 16, 40);
    this.add.text(512, 200, '训练记录', {
      fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace',
    });

    // 出口指示
    gfx.lineStyle(1, COLORS.EGO, 0.5);
    gfx.strokeRect(300, 400, 120, 38);
    this.add.text(318, 408, '[出口 → 中央区]', {
      fontSize: '6px', color: '#3fb950', fontFamily: 'monospace',
    });
  }

  _setupTriggers() {
    const R = Phaser.Geom.Rectangle;
    this.triggers = new TriggerSystem(this);
    this.triggers
      .add({
        id: 'exit_world', kind: 'proximity', type: 'exit_to_world',
        rect: new R(300, 400, 120, 38),
        onTrigger: () => this._exitToWorld(),
      })
      .add({
        id: 'obj_weight_cal', kind: 'interact', type: 'object',
        rect: new R(150, 150, 60, 60),
        objectId: 'weight_calendar', contextHint: '用户想查看体重趋势',
      })
      .add({
        id: 'obj_training_log', kind: 'interact', type: 'object',
        rect: new R(506, 142, 52, 68),
        objectId: 'training_log', contextHint: '用户想回顾训练记录',
      });
    // 健康管家 INTERACT 区由 NPC 构造函数注册
  }

  _exitToWorld() {
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.scene.start('WorldScene');
    });
  }

  _dispatchSceneChanged() {
    window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
      detail: { sceneKey: 'GymScene', roomName: '健身房' },
    }));
  }
}
