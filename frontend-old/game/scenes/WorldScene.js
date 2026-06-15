import { COLORS } from '../colors.js';
import { Player } from '../objects/Player.js';
import { TriggerSystem } from '../objects/TriggerSystem.js';
import { NPC } from '../objects/NPC.js';

// 内部渲染分辨率 720×450，zoom:2 后浏览器显示 1440×900
const SPAWN_X = 360;
const SPAWN_Y = 225;

export class WorldScene extends Phaser.Scene {
  constructor() { super({ key: 'WorldScene' }); }

  create() {
    const gfx = this.add.graphics();

    // 背景底色
    gfx.fillStyle(COLORS.BG);
    gfx.fillRect(0, 0, 720, 450);

    // 中央活动区
    gfx.fillStyle(COLORS.CARD_BG);
    gfx.fillRect(240, 150, 240, 150);
    gfx.lineStyle(1, COLORS.BORDER);
    gfx.strokeRect(240, 150, 240, 150);
    this.add.text(288, 205, '中央活动区', {
      fontSize: '8px', color: '#c9d1d9', fontFamily: 'monospace'
    });

    // 任务板（存引用供 cyber:review:done 动效使用）
    this.taskboard = this.add.rectangle(310, 190, 24, 16, COLORS.SUPEREGO, 0.7);
    this.add.text(298, 195, '[任务板]', { fontSize: '6px', color: '#0d1117', fontFamily: 'monospace' });

    // 四个房间门洞区（颜色区分 phase）
    this._drawRoom(gfx,  20,  20,  150, 90, COLORS.EGO,     '健身房\n[GYM]',    true);
    this._drawRoom(gfx, 550,  20,  150, 90, COLORS.SUPEREGO, '学习室\n[STUDY]',  false);
    this._drawRoom(gfx,  20, 340,  150, 90, COLORS.ID,       '办公室\n[OFFICE]', false);
    this._drawRoom(gfx, 550, 340,  150, 90, COLORS.BORDER,   '[预留]',           false);

    // 玩家（Player.js 提供移动、碰撞、enableInput/disableInput）
    this.player = new Player(this, SPAWN_X, SPAWN_Y);
    this._setupTriggers();

    // 赛博明翰 NPC（自动向 this.triggers 注册 INTERACT 区）
    this.npcCyber = new NPC(this, {
      npcId: 'cyber_minghan', npcName: '赛博明翰',
      spriteKey: 'npc_cyber_v1',
      x: 400, y: 235,
      triggerSystem: this.triggers,
    });

    this._setupEventBus();
    this.events.on('shutdown', this._teardownEventBus, this);

    // 淡入：create() 完毕后从黑色遮罩渐显，完成后发 scene:changed 并查通知
    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      this._dispatchSceneChanged();
      this._queryNotifications();
    });
  }

  update() {
    this.player.update();
    this.triggers.update(this.player.x, this.player.y);
  }

  _setupEventBus() {
    this._transitioning = false;
    this._handlers = {
      panelOpened:   ()  => this.player.disableInput(),
      // 仅在非场景切换状态下恢复输入；door:confirmed 后 transitioning=true，
      // 防止随后的 panel:closed 把 disableInput 覆盖掉
      panelClosed:   ()  => { if (!this._transitioning) this.player.enableInput(); },
      doorConfirmed: (e) => this._onDoorConfirmed(e.detail),
      doorCancelled: ()  => { /* cyber:panel:closed 已恢复输入，无需额外处理 */ },
      reviewDone:    ()  => this._onReviewDone(),
    };
    window.addEventListener('cyber:panel:opened',   this._handlers.panelOpened);
    window.addEventListener('cyber:panel:closed',   this._handlers.panelClosed);
    window.addEventListener('cyber:door:confirmed', this._handlers.doorConfirmed);
    window.addEventListener('cyber:door:cancelled', this._handlers.doorCancelled);
    window.addEventListener('cyber:review:done',    this._handlers.reviewDone);
  }

  _teardownEventBus() {
    window.removeEventListener('cyber:panel:opened',   this._handlers.panelOpened);
    window.removeEventListener('cyber:panel:closed',   this._handlers.panelClosed);
    window.removeEventListener('cyber:door:confirmed', this._handlers.doorConfirmed);
    window.removeEventListener('cyber:door:cancelled', this._handlers.doorCancelled);
    window.removeEventListener('cyber:review:done',    this._handlers.reviewDone);
  }

  _onDoorConfirmed({ targetScene }) {
    this._transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this._transitioning = false;
      this.scene.start(targetScene);
    });
  }

  _onReviewDone() {
    if (!this.taskboard) return;
    this.tweens.add({
      targets: this.taskboard,
      alpha: { from: 1, to: 0.15 },
      duration: 120,
      yoyo: true,
      repeat: 3,
      onComplete: () => {
        this.taskboard.setAlpha(0.7);
        this._queryNotifications();  // 审批完成后重查，角标可能清零
      },
    });
  }

  async _queryNotifications() {
    try {
      const res = await fetch('http://localhost:8000/api/notifications');
      if (!res.ok) return;
      const { count = 0 } = await res.json();
      window.dispatchEvent(new CustomEvent('cyber:notification:badge', {
        detail: { count },
      }));
      this._setTaskboardState(count > 0);
    } catch {
      // 后端未启动时静默跳过，不影响游戏运行
    }
  }

  _setTaskboardState(active) {
    if (!this.taskboard) return;
    this.taskboard.setFillStyle(COLORS.SUPEREGO, active ? 1.0 : 0.5);
    if (active) {
      this.tweens.add({
        targets: this.taskboard,
        scaleX: { from: 1, to: 1.4 },
        scaleY: { from: 1, to: 1.4 },
        duration: 180,
        yoyo: true,
      });
    }
  }

  _setupTriggers() {
    const R = Phaser.Geom.Rectangle;
    this.triggers = new TriggerSystem(this);
    this.triggers
      .add({ id: 'door_gym',    kind: 'proximity', phase: 1, type: 'door_to_gym',
             rect: new R(63, 95, 64, 28),
             targetScene: 'GymScene', roomName: '健身房', modeDescription: '进入健康管家模式' })
      .add({ id: 'door_study',  kind: 'proximity', phase: 2, type: 'door_to_study',
             rect: new R(593, 95, 64, 28), roomName: '学习室' })
      .add({ id: 'door_office', kind: 'proximity', phase: 2, type: 'door_to_office',
             rect: new R(63, 333, 64, 28), roomName: '办公室' })
      .add({ id: 'obj_taskboard', kind: 'interact', type: 'object',
             rect: new R(294, 180, 40, 24), objectId: 'taskboard' });
    // npc_cyber 的 INTERACT 区由 NPC 构造函数自动注册
  }

  _drawRoom(gfx, x, y, w, h, color, label, phase1) {
    gfx.fillStyle(color, phase1 ? 0.2 : 0.08);
    gfx.fillRect(x, y, w, h);
    gfx.lineStyle(1, color, phase1 ? 0.8 : 0.35);
    gfx.strokeRect(x, y, w, h);
    this.add.text(x + 5, y + 5, label, {
      fontSize: '7px', color: '#c9d1d9', fontFamily: 'monospace'
    });
    // 门洞指示条
    const doorX = x + w / 2 - 12;
    const doorY = (y + h / 2) > 225 ? y : y + h - 8;
    gfx.fillStyle(color, phase1 ? 0.6 : 0.2);
    gfx.fillRect(doorX, doorY, 24, 8);
  }

  _dispatchSceneChanged() {
    window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
      detail: { sceneKey: 'WorldScene', roomName: '中央区' }
    }));
  }
}
