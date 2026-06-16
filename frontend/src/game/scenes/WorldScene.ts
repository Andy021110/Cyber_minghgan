import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { NPC } from '../objects/NPC';
import { TriggerSystem } from '../objects/TriggerSystem';
import { listen } from '../../eventbus';
import type { CyberEventDetail } from '../../eventbus';

const SPAWN_X = 360;
const SPAWN_Y = 225;

export class WorldScene extends Phaser.Scene {
  private player!:       Player;
  private npcMinghan!:   NPC;
  private triggers!:     TriggerSystem;
  private taskboard!:    Phaser.GameObjects.Rectangle;
  private transitioning  = false;
  private offListeners:  Array<() => void> = [];

  constructor() { super({ key: 'WorldScene' }); }

  preload(): void {
    this.load.spritesheet('harvey', '/assets/harvey.png', { frameWidth: 16, frameHeight: 32 });
    this.load.spritesheet('kent',   '/assets/kent.png',   { frameWidth: 16, frameHeight: 32 });
    this.load.image('floors', '/assets/stardew/Floors.png');
  }

  create(): void {
    this.drawLayout();
    // Floor — tiled texture, depth 0 (behind objects)
    this.add.tileSprite(360, 225, 640, 380, 'floors').setDepth(0).setAlpha(0.5);
    this.taskboard = this.add.rectangle(310, 190, 24, 16, COLORS.SUPEREGO, 0.7);
    this.add.text(298, 195, '[任务板]', { fontSize: '6px', color: '#0d1117', fontFamily: 'monospace' });

    this.player = new Player(this, SPAWN_X, SPAWN_Y);
    this.setupTriggers();

    this.npcMinghan = new NPC(this, {
      npcId: 'cyber_minghan', npcName: '赛博明翰',
      spriteKey: 'harvey', x: 400, y: 235,
      patrol: { x1: 385, x2: 415, speed: 25 },
      triggerSystem: this.triggers,
    });

    this.setupEventBus();
    this.events.on('shutdown', this.teardownEventBus, this);

    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      this.dispatchSceneChanged();
      void this.queryNotifications();
    });
  }

  update(_time: number, delta: number): void {
    this.player.update();
    this.npcMinghan.update(delta);
    this.triggers.update(this.player.x, this.player.y);
  }

  private drawLayout(): void {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG);
    gfx.fillRect(0, 0, 720, 450);
    gfx.fillStyle(COLORS.CARD_BG);
    gfx.fillRect(240, 150, 240, 150);
    gfx.lineStyle(1, COLORS.BORDER);
    gfx.strokeRect(240, 150, 240, 150);
    this.add.text(288, 205, '中央活动区', { fontSize: '8px', color: '#c9d1d9', fontFamily: 'monospace' });
    this.drawRoom(gfx,  20,  20, 150, 90, COLORS.EGO,      '健身房\n[GYM]',    true);
    this.drawRoom(gfx, 550,  20, 150, 90, COLORS.SUPEREGO,  '学习室\n[STUDY]',  false);
    this.drawRoom(gfx,  20, 340, 150, 90, COLORS.ID,        '办公室\n[OFFICE]', false);
    this.drawRoom(gfx, 550, 340, 150, 90, COLORS.BORDER,    '[预留]',           false);
  }

  private drawRoom(gfx: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number,
                   color: number, label: string, phase1: boolean): void {
    gfx.fillStyle(color, phase1 ? 0.2 : 0.08);
    gfx.fillRect(x, y, w, h);
    gfx.lineStyle(1, color, phase1 ? 0.8 : 0.35);
    gfx.strokeRect(x, y, w, h);
    this.add.text(x + 5, y + 5, label, { fontSize: '7px', color: '#c9d1d9', fontFamily: 'monospace' });
    const doorX = x + w / 2 - 12;
    const doorY = (y + h / 2) > 225 ? y : y + h - 8;
    gfx.fillStyle(color, phase1 ? 0.6 : 0.2);
    gfx.fillRect(doorX, doorY, 24, 8);
  }

  private setupTriggers(): void {
    const R = Phaser.Geom.Rectangle;
    this.triggers = new TriggerSystem(this);
    this.triggers
      .add({ id: 'door_gym',     kind: 'proximity', phase: 1, type: 'door_to_gym',
             rect: new R(63,  95,  64, 28), targetScene: 'GymScene',
             roomName: '健身房', modeDescription: '进入健康管家模式' })
      .add({ id: 'door_study',   kind: 'proximity', phase: 2, type: 'door_to_study',
             rect: new R(593, 95,  64, 28), targetScene: 'StudyScene', roomName: '学习室' })
      .add({ id: 'door_office',  kind: 'proximity', phase: 2, type: 'door_to_office',
             rect: new R(63,  333, 64, 28), targetScene: 'OfficeScene', roomName: '办公室' })
      .add({ id: 'obj_taskboard', kind: 'interact', type: 'object',
             rect: new R(294, 180, 40, 24), objectId: 'taskboard' })
      .add({ id: 'obj_bookshelf', kind: 'interact', type: 'examine',
             rect: new R(60, 170, 40, 40),
             roomName: '书架',
             examineQuery: '（检查书架）我最近有哪些新发现或学到的东西？' });
  }

  private setupEventBus(): void {
    this.offListeners = [
      listen('cyber:panel:opened',   ()  => this.player.disableInput()),
      listen('cyber:panel:closed',   ()  => { if (!this.transitioning) this.player.enableInput(); }),
      listen('cyber:door:confirmed', (e) => this.onDoorConfirmed(e)),
      listen('cyber:door:cancelled', ()  => { /* panel:closed already re-enables input */ }),
      listen('cyber:review:done',    ()  => this.onReviewDone()),
    ];
  }

  private teardownEventBus(): void {
    this.offListeners.forEach(off => off());
    this.offListeners = [];
  }

  private onDoorConfirmed({ targetScene }: CyberEventDetail['cyber:door:confirmed']): void {
    this.transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.transitioning = false;
      this.scene.start(targetScene);
    });
  }

  private onReviewDone(): void {
    this.tweens.add({
      targets: this.taskboard, alpha: { from: 1, to: 0.15 },
      duration: 120, yoyo: true, repeat: 3,
      onComplete: () => { this.taskboard.setAlpha(0.7); void this.queryNotifications(); },
    });
  }

  private async queryNotifications(): Promise<void> {
    try {
      const res = await fetch('http://localhost:8000/api/notifications');
      if (!res.ok) return;
      const { count = 0 } = (await res.json()) as { count: number };
      window.dispatchEvent(new CustomEvent('cyber:notification:badge', { detail: { count } }));
      this.setTaskboardState(count > 0);
    } catch { /* backend offline — silently skip */ }
  }

  private setTaskboardState(active: boolean): void {
    this.taskboard.setFillStyle(COLORS.SUPEREGO, active ? 1.0 : 0.5);
    if (active) {
      this.tweens.add({
        targets: this.taskboard,
        scaleX: { from: 1, to: 1.4 }, scaleY: { from: 1, to: 1.4 },
        duration: 180, yoyo: true,
      });
    }
  }

  private dispatchSceneChanged(): void {
    window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
      detail: { sceneKey: 'WorldScene', roomName: '中央区' },
    }));
  }
}
