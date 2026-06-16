import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { listen } from '../../eventbus';

export class OfficeScene extends Phaser.Scene {
  private player!:      Player;
  private transitioning = false;
  private offListeners: Array<() => void> = [];

  constructor() { super({ key: 'OfficeScene' }); }

  preload(): void {
    this.load.spritesheet('harvey', '/assets/harvey.png', { frameWidth: 16, frameHeight: 32 });
    this.load.spritesheet('kent',   '/assets/kent.png',   { frameWidth: 16, frameHeight: 32 });
    this.load.image('floors', '/assets/stardew/Floors.png');
  }

  create(): void {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG); gfx.fillRect(0, 0, 720, 450);
    this.add.text(260, 180, '🚧 办公室\n即将开放', {
      fontSize: '12px', color: '#f0a500', fontFamily: 'monospace', align: 'center',
    });
    this.player = new Player(this, 360, 380);
    this.offListeners = [
      listen('cyber:panel:opened', () => this.player.disableInput()),
      listen('cyber:panel:closed', () => { if (!this.transitioning) this.player.enableInput(); }),
    ];
    this.events.on('shutdown', () => { this.offListeners.forEach(off => off()); }, this);
    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
        detail: { sceneKey: 'OfficeScene', roomName: '办公室' },
      }));
    });
  }

  update(): void {
    this.player.update();
    if (this.player.y > 420 && !this.transitioning) this.exitToWorld();
  }

  private exitToWorld(): void {
    this.transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.transitioning = false;
      this.scene.start('WorldScene');
    });
  }
}
