import Phaser from 'phaser';
import { Player } from '../objects/Player';
import { NPC } from '../objects/NPC';
import { TriggerSystem } from '../objects/TriggerSystem';
import { listen } from '../../eventbus';

// JoshHouse: 25×25 tiles × 16px × scale-1 = 400×400 world (fits in 720×450 viewport)
const MAP_SCALE = 1;
const TILE_PX   = 16 * MAP_SCALE;

// Player enters from WorldScene — spawn near the bottom entry area (tile 9, 22)
const SPAWN_X = 9  * TILE_PX + TILE_PX / 2;
const SPAWN_Y = 21 * TILE_PX;

export class GymScene extends Phaser.Scene {
  private player!:       Player;
  private npcAlex!:      NPC;
  private triggers!:     TriggerSystem;
  private transitioning  = false;
  private offListeners:  Array<() => void> = [];

  constructor() { super({ key: 'GymScene' }); }

  preload(): void {
    this.load.tilemapTiledJSON('joshhouse', '/assets/maps/option_c_joshhouse.json');
    this.load.image('townInterior',   '/assets/maps/townInterior.png');
    this.load.image('townInterior_2', '/assets/maps/townInterior_2.png');
    this.load.image('paths',          '/assets/maps/paths.png');
    this.load.spritesheet('alex', '/assets/alex.png', { frameWidth: 16, frameHeight: 32 });
    this.load.spritesheet('kent', '/assets/kent.png', { frameWidth: 16, frameHeight: 32 });
  }

  create(): void {
    this.buildTilemap();

    this.player   = new Player(this, SPAWN_X, SPAWN_Y);
    this.triggers = new TriggerSystem(this);
    this.cameras.main.centerOn(200, 200);

    const R = Phaser.Geom.Rectangle;

    // Alex patrols the gym (green-floor area, roughly tiles 13–22, row 18)
    this.npcAlex = new NPC(this, {
      npcId: 'health_coach', npcName: '健康管家',
      spriteKey: 'alex', x: 17 * TILE_PX, y: 18 * TILE_PX,
      patrol: { x1: 13 * TILE_PX, x2: 22 * TILE_PX, speed: 45 },
      triggerSystem: this.triggers,
    });

    // Exit back to WorldScene — bottom entry tile (9, 24)
    this.triggers.add({
      id: 'exit_to_world', kind: 'proximity', type: 'exit',
      rect: new R(7 * TILE_PX, 23 * TILE_PX, 4 * TILE_PX, 2 * TILE_PX),
      onTrigger: () => { this.exitToWorld(); },
    });

    this.offListeners = [
      listen('cyber:panel:opened', () => { this.player.disableInput(); this.npcAlex.pause(); }),
      listen('cyber:panel:closed', () => { if (!this.transitioning) { this.player.enableInput(); this.npcAlex.resume(); } }),
    ];
    this.events.on('shutdown', () => { this.offListeners.forEach(off => off()); }, this);

    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
        detail: { sceneKey: 'GymScene', roomName: '健身房' },
      }));
    });
  }

  update(_time: number, delta: number): void {
    this.player.update();
    this.npcAlex.update(delta);
    this.triggers.update(this.player.x, this.player.y);
  }

  private buildTilemap(): void {
    const map = this.make.tilemap({ key: 'joshhouse' });
    const ts1  = map.addTilesetImage('townInterior',   'townInterior')!;
    const ts2  = map.addTilesetImage('townInterior_2', 'townInterior_2')!;
    const tsP  = map.addTilesetImage('paths',          'paths')!;
    const all  = [ts1, ts2, tsP];

    map.createLayer('Back',      all, 0, 0)!.setScale(MAP_SCALE).setDepth(0);
    map.createLayer('Back2',     all, 0, 0)!.setScale(MAP_SCALE).setDepth(1);
    map.createLayer('Buildings', all, 0, 0)!.setScale(MAP_SCALE).setDepth(2);
    map.createLayer('Front',     all, 0, 0)!.setScale(MAP_SCALE).setDepth(15);
    map.createLayer('Front2',    all, 0, 0)!.setScale(MAP_SCALE).setDepth(16);
    map.createLayer('Front3',    all, 0, 0)!.setScale(MAP_SCALE).setDepth(17);
    map.createLayer('Paths',     all, 0, 0)!.setVisible(false);

    this.physics.world.setBounds(0, 0, map.widthInPixels * MAP_SCALE, map.heightInPixels * MAP_SCALE);
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
