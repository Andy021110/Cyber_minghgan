import Phaser from 'phaser';

const SPEED = 80;

export class Player {
  private inputEnabled = true;
  private direction    = 'idle_down';
  private sprite:      Phaser.Physics.Arcade.Sprite;
  private body:        Phaser.Physics.Arcade.Body;
  private cursors:     Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd:        Record<string, Phaser.Input.Keyboard.Key>;

  constructor(scene: Phaser.Scene, x: number, y: number) {
    this.sprite = scene.physics.add.sprite(x, y, 'kent');
    this.sprite.setTint(0x7ecfff);   // blue tint = player
    this.sprite.setScale(1);         // 16px → 1 tile wide, 2 tiles tall (SDV proportion)
    this.sprite.setDepth(10);

    this.body = this.sprite.body as Phaser.Physics.Arcade.Body;
    this.body.setCollideWorldBounds(true);
    this.body.setSize(12, 16);       // tight collision box (unscaled)
    this.body.setOffset(2, 16);      // align feet to bottom

    // Create animations (idempotent — Phaser skips if already exists)
    const anims = scene.anims;
    if (!anims.exists('player_walk_down')) {
      anims.create({ key: 'player_walk_down',  frames: anims.generateFrameNumbers('kent', { start: 0,  end: 3  }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_walk_right', frames: anims.generateFrameNumbers('kent', { start: 4,  end: 7  }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_walk_up',    frames: anims.generateFrameNumbers('kent', { start: 8,  end: 11 }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_walk_left',  frames: anims.generateFrameNumbers('kent', { start: 12, end: 15 }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_idle_down',  frames: anims.generateFrameNumbers('kent', { start: 0,  end: 0  }), frameRate: 1, repeat: -1 });
    }
    this.sprite.play('player_idle_down');

    this.cursors = scene.input.keyboard!.createCursorKeys();
    this.wasd = scene.input.keyboard!.addKeys({
      up:    Phaser.Input.Keyboard.KeyCodes.W,
      down:  Phaser.Input.Keyboard.KeyCodes.S,
      left:  Phaser.Input.Keyboard.KeyCodes.A,
      right: Phaser.Input.Keyboard.KeyCodes.D,
    }) as Record<string, Phaser.Input.Keyboard.Key>;
  }

  update(): void {
    if (!this.inputEnabled) {
      this.body.setVelocity(0, 0);
      return;
    }

    let vx = 0, vy = 0;
    if (this.cursors.left.isDown  || this.wasd['left'].isDown)  vx = -SPEED;
    if (this.cursors.right.isDown || this.wasd['right'].isDown) vx =  SPEED;
    if (this.cursors.up.isDown    || this.wasd['up'].isDown)    vy = -SPEED;
    if (this.cursors.down.isDown  || this.wasd['down'].isDown)  vy =  SPEED;
    if (vx !== 0 && vy !== 0) { vx *= 0.707; vy *= 0.707; }

    this.body.setVelocity(vx, vy);

    if      (vx < 0) this._play('player_walk_left');
    else if (vx > 0) this._play('player_walk_right');
    else if (vy < 0) this._play('player_walk_up');
    else if (vy > 0) this._play('player_walk_down');
    else             this._play('player_idle_down');
  }

  private _play(key: string): void {
    if (this.direction !== key) {
      this.direction = key;
      this.sprite.play(key);
    }
  }

  enableInput():  void { this.inputEnabled = true; }
  disableInput(): void { this.inputEnabled = false; this.body.setVelocity(0, 0); }

  get x(): number { return this.sprite.x; }
  get y(): number { return this.sprite.y; }
  get gameObject(): Phaser.GameObjects.GameObject { return this.sprite; }
}
