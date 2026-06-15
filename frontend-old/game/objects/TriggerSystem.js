// 通用触发区检测系统，WorldScene / GymScene 共用。
// zone 结构: { id, kind: 'proximity'|'interact', rect, type, ...meta, onTrigger? }
export class TriggerSystem {
  constructor(scene) {
    this.scene = scene;
    this.zones = [];
    this._insideIds = new Set();  // 已在其中的 proximity zone id，防止持续重复触发
    this.eKey = scene.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.E);
  }

  add(zone) { this.zones.push(zone); return this; }

  update(playerX, playerY) {
    for (const zone of this.zones) {
      const inside = Phaser.Geom.Rectangle.Contains(zone.rect, playerX, playerY);

      if (zone.kind === 'proximity') {
        if (inside && !this._insideIds.has(zone.id)) {
          this._insideIds.add(zone.id);
          this._fireProximity(zone);
        } else if (!inside) {
          this._insideIds.delete(zone.id);
        }
      } else if (zone.kind === 'interact' && inside) {
        if (Phaser.Input.Keyboard.JustDown(this.eKey)) {
          this._fireInteract(zone);
        }
      }
    }
  }

  _fireProximity(zone) {
    if (zone.onTrigger) { zone.onTrigger(); return; }

    if (zone.phase > 1) {
      this._showHint('即将开放');
      return;
    }
    if (zone.type.startsWith('door_to')) {
      window.dispatchEvent(new CustomEvent('cyber:door:approach', {
        detail: {
          targetScene: zone.targetScene,
          roomName: zone.roomName,
          modeDescription: zone.modeDescription,
        },
      }));
    }
  }

  _fireInteract(zone) {
    if (zone.onTrigger) { zone.onTrigger(); return; }

    if (zone.type === 'npc') {
      window.dispatchEvent(new CustomEvent('cyber:npc:interact', {
        detail: { npcId: zone.npcId, npcName: zone.npcName },
      }));
    } else if (zone.type === 'object') {
      window.dispatchEvent(new CustomEvent('cyber:object:interact', {
        detail: { objectId: zone.objectId, contextHint: zone.contextHint ?? null },
      }));
    }
  }

  // Phase 2 门洞：在 canvas 内显示临时提示，不发 EventBus 事件
  _showHint(msg) {
    const { width, height } = this.scene.cameras.main;
    const t = this.scene.add.text(width / 2, height / 2 - 60, msg, {
      fontSize: '9px', color: '#f0a500', fontFamily: 'monospace',
      backgroundColor: '#161b22', padding: { x: 8, y: 5 },
    }).setOrigin(0.5).setDepth(10);
    this.scene.time.delayedCall(1800, () => t.destroy());
  }
}
