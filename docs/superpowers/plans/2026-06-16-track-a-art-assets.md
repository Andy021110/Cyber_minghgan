# Track A: Art Assets Implementation Plan

**Goal:** Replace Phaser rectangle placeholders with real sprites. Player → Sebastian sprite (blue tint). NPC → Sebastian sprite (default). WorldScene/GymScene → wood/stone floor tiles.

**Tech Stack:** Phaser 3.90, TypeScript 5, Stardew Valley extracted PNGs

**Key sprite facts:**
- `Sebastian.png`: 64×480px, frameWidth=16, frameHeight=32, 4 cols × 15 rows
  - frames 0-3: walk_down, frames 4-7: walk_right, frames 8-11: walk_up, frames 12-15: walk_left
- `Floors.png`: 64×336px (tile reference for floor color/texture)
- All assets go to `frontend/public/assets/stardew/`

---

### Task A1: Copy assets

**Files:**
- Source: `raw-assets/stardew/extracted/Characters/Sebastian.png`
- Source: `raw-assets/stardew/extracted/TileSheets/Floors.png`
- Dest: `frontend/public/assets/stardew/`

- [ ] Run:
```bash
mkdir -p frontend/public/assets/stardew
cp raw-assets/stardew/extracted/Characters/Sebastian.png frontend/public/assets/stardew/
cp raw-assets/stardew/extracted/TileSheets/Floors.png frontend/public/assets/stardew/
```
- [ ] Verify files exist with `ls frontend/public/assets/stardew/`
- [ ] Commit: `git add frontend/public/assets/stardew/ && git commit -m "feat: add stardew character and floor sprites"`

---

### Task A2: Add preload() to WorldScene and GymScene

**Files:**
- Modify: `frontend/src/game/scenes/WorldScene.ts`
- Modify: `frontend/src/game/scenes/GymScene.ts`

Both scenes need a `preload()` lifecycle method added before `create()`:

```typescript
preload(): void {
  this.load.spritesheet('sebastian', '/assets/stardew/Sebastian.png', {
    frameWidth: 16, frameHeight: 32,
  });
  this.load.image('floors', '/assets/stardew/Floors.png');
}
```

- [ ] Add `preload()` method to WorldScene.ts (insert before the `create()` method)
- [ ] Add `preload()` method to GymScene.ts (insert before the `create()` method)
- [ ] Run `cd frontend && npx tsc --noEmit` — expect no errors
- [ ] Commit: `git add frontend/src/game/scenes/ && git commit -m "feat: add preload for stardew sprites in game scenes"`

---

### Task A3: Replace Player rectangle with Sebastian sprite

**Files:**
- Modify: `frontend/src/game/objects/Player.ts`

Current code uses `scene.add.rectangle()`. Replace with `scene.physics.add.sprite()`.

**Full updated Player.ts:**

```typescript
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
    this.sprite = scene.physics.add.sprite(x, y, 'sebastian');
    this.sprite.setTint(0x7ecfff);   // blue tint = player
    this.sprite.setScale(2);         // 16px → 32px on screen
    this.sprite.setDepth(10);

    this.body = this.sprite.body as Phaser.Physics.Arcade.Body;
    this.body.setCollideWorldBounds(true);
    this.body.setSize(12, 16);       // tight collision box (unscaled)
    this.body.setOffset(2, 16);      // align feet to bottom

    // Create animations (idempotent — Phaser skips if already exists)
    const anims = scene.anims;
    if (!anims.exists('player_walk_down')) {
      anims.create({ key: 'player_walk_down',  frames: anims.generateFrameNumbers('sebastian', { start: 0,  end: 3  }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_walk_right', frames: anims.generateFrameNumbers('sebastian', { start: 4,  end: 7  }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_walk_up',    frames: anims.generateFrameNumbers('sebastian', { start: 8,  end: 11 }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_walk_left',  frames: anims.generateFrameNumbers('sebastian', { start: 12, end: 15 }), frameRate: 8, repeat: -1 });
      anims.create({ key: 'player_idle_down',  frames: anims.generateFrameNumbers('sebastian', { start: 0,  end: 0  }), frameRate: 1, repeat: -1 });
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
}
```

- [ ] Replace full content of `frontend/src/game/objects/Player.ts` with the code above
- [ ] Run `cd frontend && npx tsc --noEmit` — expect no errors
- [ ] Run `cd frontend && npx vitest run 2>&1 | tail -5` — all tests must pass (Player has no direct tests, but App.test.tsx must still pass)
- [ ] Commit: `git add frontend/src/game/objects/Player.ts && git commit -m "feat: replace Player rectangle with Sebastian sprite + walk animations"`

---

### Task A4: Replace NPC rectangle with Sebastian sprite

**Files:**
- Modify: `frontend/src/game/objects/NPC.ts`

NPC uses `spriteKey` but currently ignores it. Now use it.

**Full updated NPC.ts:**

```typescript
import Phaser from 'phaser';
import type { TriggerSystem } from './TriggerSystem';

export interface NPCOpts {
  npcId:          string;
  npcName:        string;
  spriteKey:      string;
  x:              number;
  y:              number;
  triggerSystem?: TriggerSystem;
}

export class NPC {
  readonly npcId:   string;
  readonly npcName: string;
  private sprite:   Phaser.GameObjects.Sprite;
  private label:    Phaser.GameObjects.Text;

  constructor(scene: Phaser.Scene, opts: NPCOpts) {
    const { npcId, npcName, spriteKey, x, y, triggerSystem } = opts;
    this.npcId   = npcId;
    this.npcName = npcName;

    this.sprite = scene.add.sprite(x, y, spriteKey);
    this.sprite.setScale(2);
    this.sprite.setDepth(10);

    // Create idle animation (idempotent)
    const animKey = `${spriteKey}_idle`;
    if (!scene.anims.exists(animKey)) {
      scene.anims.create({
        key: animKey,
        frames: scene.anims.generateFrameNumbers(spriteKey, { start: 0, end: 3 }),
        frameRate: 4,
        repeat: -1,
      });
    }
    this.sprite.play(animKey);

    this.label = scene.add.text(x, y - 28, npcName, {
      fontSize: '6px', color: '#f0d090', fontFamily: 'monospace',
    }).setOrigin(0.5).setDepth(11);

    if (triggerSystem) {
      triggerSystem.add({
        id: `npc_${npcId}`, kind: 'interact', type: 'npc',
        rect: new Phaser.Geom.Rectangle(x - 24, y - 26, 48, 52),
        npcId, npcName,
      });
    }
  }

  destroy(): void {
    this.sprite.destroy();
    this.label.destroy();
  }
}
```

- [ ] Replace full content of `frontend/src/game/objects/NPC.ts` with the code above
- [ ] Run `cd frontend && npx tsc --noEmit` — expect no errors
- [ ] Run `cd frontend && npx vitest run 2>&1 | tail -5` — all tests must pass
- [ ] Commit: `git add frontend/src/game/objects/NPC.ts && git commit -m "feat: replace NPC rectangle with spritesheet + idle animation"`

---

### Task A5: Add floor rendering to WorldScene and GymScene

**Files:**
- Modify: `frontend/src/game/scenes/WorldScene.ts`
- Modify: `frontend/src/game/scenes/GymScene.ts`

Use `scene.add.tileSprite()` to render a repeating floor texture. Place it behind existing graphics (setDepth 0).

In WorldScene `create()`, after `gfx.fillRect` for the room interior, add:
```typescript
// Floor — tiled texture, depth 0 (behind objects)
this.add.tileSprite(360, 225, 640, 380, 'floors').setDepth(0).setAlpha(0.5);
```

In GymScene `create()`, same approach with slightly different color area:
```typescript
this.add.tileSprite(360, 230, 640, 380, 'floors').setDepth(0).setAlpha(0.45);
```

- [ ] Add tileSprite call to WorldScene.ts `create()` after the gfx.fillRect background
- [ ] Add tileSprite call to GymScene.ts `create()` after the gfx.fillRect background
- [ ] Run `cd frontend && npx tsc --noEmit` — expect no errors
- [ ] Commit: `git add frontend/src/game/scenes/ && git commit -m "feat: add tiled floor texture to WorldScene and GymScene"`

---

### Final check

- [ ] Run `cd frontend && npx vitest run` — all tests pass
- [ ] Run `cd frontend && npx tsc --noEmit` — no errors
- [ ] Report: total tests passing, any visual notes
