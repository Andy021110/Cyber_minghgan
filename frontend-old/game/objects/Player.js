import { COLORS } from '../colors.js';

const SPEED = 80;

// 占位阶段：用矩形填充色变化代替方向帧动画
const DIR_COLOR = {
  idle:       COLORS.EGO,
  walk_down:  0x5fd96a,
  walk_up:    0x2da83b,
  walk_left:  0x1e8f2e,
  walk_right: 0x7fff8a,
};

export class Player {
  constructor(scene, x, y) {
    this.scene = scene;
    this._inputEnabled = true;
    this._direction = 'idle';

    // 占位矩形 + arcade 物理体（G12 替换为 spritesheet）
    this.sprite = scene.add.rectangle(x, y, 14, 22, COLORS.EGO);
    scene.physics.add.existing(this.sprite);
    this.body = this.sprite.body;
    this.body.setCollideWorldBounds(true);

    this.cursors = scene.input.keyboard.createCursorKeys();
    this.wasd = scene.input.keyboard.addKeys({
      up:    Phaser.Input.Keyboard.KeyCodes.W,
      down:  Phaser.Input.Keyboard.KeyCodes.S,
      left:  Phaser.Input.Keyboard.KeyCodes.A,
      right: Phaser.Input.Keyboard.KeyCodes.D,
    });
  }

  update() {
    if (!this._inputEnabled) {
      this.body.setVelocity(0, 0);
      return;
    }

    const { cursors, wasd } = this;
    let vx = 0, vy = 0;

    if (cursors.left.isDown  || wasd.left.isDown)  vx = -SPEED;
    if (cursors.right.isDown || wasd.right.isDown) vx =  SPEED;
    if (cursors.up.isDown    || wasd.up.isDown)    vy = -SPEED;
    if (cursors.down.isDown  || wasd.down.isDown)  vy =  SPEED;

    // 斜向移动归一化
    if (vx !== 0 && vy !== 0) { vx *= 0.707; vy *= 0.707; }

    this.body.setVelocity(vx, vy);

    let dir = 'idle';
    if      (vx < 0) dir = 'walk_left';
    else if (vx > 0) dir = 'walk_right';
    else if (vy < 0) dir = 'walk_up';
    else if (vy > 0) dir = 'walk_down';

    if (dir !== this._direction) {
      this._direction = dir;
      this.sprite.setFillStyle(DIR_COLOR[dir]);
    }
  }

  enableInput()  { this._inputEnabled = true; }
  disableInput() { this._inputEnabled = false; this.body.setVelocity(0, 0); }

  get x() { return this.sprite.x; }
  get y() { return this.sprite.y; }
}
