import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { NPC } from '../objects/NPC';
import { TriggerSystem } from '../objects/TriggerSystem';
import { listen } from '../../eventbus';
import type { CyberEventDetail } from '../../eventbus';

// SamHouse: 25×25 tiles × 16px × scale-1 = 400×400 world
// Phaser viewport is 720×450, so the whole map is visible at once (no scrolling)
const MAP_SCALE  = 1;
const TILE_PX    = 16 * MAP_SCALE;   // 32 px per tile in world coords
// Warp exit at tile (4, 24) — player enters from town via bottom
const SPAWN_X    = 4  * TILE_PX + TILE_PX / 2;   // 144
const SPAWN_Y    = 22 * TILE_PX;                  // 704  (2 tiles above warp)

export class WorldScene extends Phaser.Scene {
  private player!:       Player;
  private npcMinghan!:   NPC;
  private triggers!:     TriggerSystem;
  private taskboard!:    Phaser.GameObjects.Rectangle;
  private transitioning  = false;
  private offListeners:  Array<() => void> = [];

  constructor() { super({ key: 'WorldScene' }); }

  preload(): void {
    this.load.tilemapTiledJSON('samhouse', '/assets/maps/option_a_samhouse.json');
    this.load.image('townInterior',   '/assets/maps/townInterior.png');
    this.load.image('townInterior_2', '/assets/maps/townInterior_2.png');
    this.load.image('paths',          '/assets/maps/paths.png');
    this.load.spritesheet('harvey', '/assets/harvey.png', { frameWidth: 16, frameHeight: 32 });
    this.load.spritesheet('kent',   '/assets/kent.png',   { frameWidth: 16, frameHeight: 32 });
  }

  create(): void {
    this.buildTilemap();

    this.player = new Player(this, SPAWN_X, SPAWN_Y);
    // Map (400×400) fits inside viewport (720×450) — center it, no scroll needed
    this.cameras.main.centerOn(200, 200);

    // Taskboard: living-room area, near tile (7, 10)
    const tbX = 7 * TILE_PX, tbY = 10 * TILE_PX;
    this.taskboard = this.add.rectangle(tbX, tbY, 24, 16, COLORS.SUPEREGO, 0.7).setDepth(3);
    this.add.text(tbX - 12, tbY + 3, '[任务板]', {
      fontSize: '6px', color: '#0d1117', fontFamily: 'monospace',
    }).setDepth(3);

    this.setupTriggers();

    // Harvey patrols the main living-room corridor, tile cols 6-10, row 13
    this.npcMinghan = new NPC(this, {
      npcId: 'cyber_minghan', npcName: '赛博明翰',
      spriteKey: 'harvey', x: 8 * TILE_PX, y: 13 * TILE_PX,
      patrol: { x1: 6 * TILE_PX, x2: 10 * TILE_PX, speed: 25 },
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

  // ── Private ───────────────────────────────────────────────────────────────

  private buildTilemap(): void {
    const map = this.make.tilemap({ key: 'samhouse' });

    const ts1 = map.addTilesetImage('townInterior',   'townInterior')!;
    const ts2 = map.addTilesetImage('townInterior_2', 'townInterior_2')!;
    const tsP = map.addTilesetImage('paths',          'paths')!;
    const all = [ts1, ts2, tsP];

    // Depth order: Back(0) < Back2(1) < Buildings(2) < player/NPC(10) < Front(15) < AlwaysFront(25)
    map.createLayer('Back',         all, 0, 0)!.setScale(MAP_SCALE).setDepth(0);
    map.createLayer('Back2',        all, 0, 0)!.setScale(MAP_SCALE).setDepth(1);
    map.createLayer('Buildings',    all, 0, 0)!.setScale(MAP_SCALE).setDepth(2);
    map.createLayer('Front',        all, 0, 0)!.setScale(MAP_SCALE).setDepth(15);
    map.createLayer('Front2',       all, 0, 0)!.setScale(MAP_SCALE).setDepth(16);
    map.createLayer('AlwaysFront',  all, 0, 0)!.setScale(MAP_SCALE).setDepth(25);
    map.createLayer('AlwaysFront2', all, 0, 0)!.setScale(MAP_SCALE).setDepth(26);
    map.createLayer('Paths',        all, 0, 0)!.setVisible(false);  // logic layer

    const worldW = map.widthInPixels  * MAP_SCALE;   // 400
    const worldH = map.heightInPixels * MAP_SCALE;   // 400
    this.physics.world.setBounds(0, 0, worldW, worldH);
    // No camera bounds — map fits inside viewport, camera stays centered
  }

  private setupTriggers(): void {
    const R = Phaser.Geom.Rectangle;
    this.triggers = new TriggerSystem(this);

    // Door positions from SamHouse TMX: tile (12,14), (17,6), (11,18)
    // Each trigger rect is centered on the door tile (32×32 at scale-2)
    this.triggers
      .add({ id: 'door_gym',    kind: 'proximity', phase: 1, type: 'door_to_gym',
             rect: new R(12*TILE_PX - 16, 14*TILE_PX - 16, 48, 48),
             targetScene: 'GymScene', roomName: '健身房', modeDescription: '进入健康管家模式' })
      .add({ id: 'door_study',  kind: 'proximity', phase: 2, type: 'door_to_study',
             rect: new R(17*TILE_PX - 16, 6*TILE_PX - 16, 48, 48),
             targetScene: 'StudyScene', roomName: '学习室' })
      .add({ id: 'door_office', kind: 'proximity', phase: 2, type: 'door_to_office',
             rect: new R(11*TILE_PX - 16, 18*TILE_PX - 16, 48, 48),
             targetScene: 'OfficeScene', roomName: '办公室' })
      .add({ id: 'obj_taskboard', kind: 'interact', type: 'object',
             rect: new R(7*TILE_PX - 16, 10*TILE_PX - 16, 56, 40), objectId: 'taskboard' })
      .add({ id: 'obj_bookshelf', kind: 'interact', type: 'examine',
             rect: new R(3*TILE_PX - 16, 11*TILE_PX - 16, 48, 48),
             roomName: '书架', examineQuery: '（检查书架）我最近有哪些新发现或学到的东西？' });
  }

  private setupEventBus(): void {
    this.offListeners = [
      listen('cyber:panel:opened',   ()  => { this.player.disableInput(); this.npcMinghan.pause(); }),
      listen('cyber:panel:closed',   ()  => { if (!this.transitioning) { this.player.enableInput(); this.npcMinghan.resume(); } }),
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
