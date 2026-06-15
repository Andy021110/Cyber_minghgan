import Phaser from 'phaser';
import { COLORS } from '../colors';

const SPEED = 80;

const DIR_COLOR: Record<string, number> = {
  idle:       COLORS.EGO,
  walk_down:  0x5fd96a,
  walk_up:    0x2da83b,
  walk_left:  0x1e8f2e,
  walk_right: 0x7fff8a,
};

export class Player {
  private inputEnabled = true;
  private direction    = 'idle';
  private sprite:      Phaser.GameObjects.Rectangle;
  private body:        Phaser.Physics.Arcade.Body;
  private cursors:     Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd:        Record<string, Phaser.Input.Keyboard.Key>;

  constructor(scene: Phaser.Scene, x: number, y: number) {
    this.sprite = scene.add.rectangle(x, y, 14, 22, COLORS.EGO);
    scene.physics.add.existing(this.sprite);
    this.body = this.sprite.body as Phaser.Physics.Arcade.Body;
    this.body.setCollideWorldBounds(true);

    this.cursors = scene.input.keyboard!.createCursorKeys();
    this.wasd = scene.input.keyboard!.addKeys({
      up:    Phaser.Input.Keyboard.KeyCodes.W,
      down:  Phaser.Input.Keyboard.KeyCodes.S,
      left:  Phaser.Input.Keyboard.KeyCodes.A,
      right: Phaser.Input.Keyboard.KeyCodes.D,
    }) as Record<string, Phaser.Input.Keyboard.Key>;
  }

  update(): void {
    if (!this.inputEnabled) { this.body.setVelocity(0, 0); return; }

    let vx = 0, vy = 0;
    if (this.cursors.left.isDown  || this.wasd['left'].isDown)  vx = -SPEED;
    if (this.cursors.right.isDown || this.wasd['right'].isDown) vx =  SPEED;
    if (this.cursors.up.isDown    || this.wasd['up'].isDown)    vy = -SPEED;
    if (this.cursors.down.isDown  || this.wasd['down'].isDown)  vy =  SPEED;
    if (vx !== 0 && vy !== 0) { vx *= 0.707; vy *= 0.707; }

    this.body.setVelocity(vx, vy);

    let dir = 'idle';
    if      (vx < 0) dir = 'walk_left';
    else if (vx > 0) dir = 'walk_right';
    else if (vy < 0) dir = 'walk_up';
    else if (vy > 0) dir = 'walk_down';

    if (dir !== this.direction) {
      this.direction = dir;
      this.sprite.setFillStyle(DIR_COLOR[dir]);
    }
  }

  enableInput():  void { this.inputEnabled = true; }
  disableInput(): void { this.inputEnabled = false; this.body.setVelocity(0, 0); }

  get x(): number { return this.sprite.x; }
  get y(): number { return this.sprite.y; }
}
