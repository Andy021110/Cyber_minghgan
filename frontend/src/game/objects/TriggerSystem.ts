import Phaser from 'phaser';
import { dispatch } from '../../eventbus';

export interface TriggerZone {
  id:               string;
  kind:             'proximity' | 'interact';
  rect:             Phaser.Geom.Rectangle;
  phase?:           number;
  type:             string;
  targetScene?:     string;
  roomName?:        string;
  modeDescription?: string;
  objectId?:        string;
  contextHint?:     string;
  npcId?:           string;
  npcName?:         string;
  examineQuery?:    string;
  onTrigger?:       () => void;
}

export class TriggerSystem {
  private zones:     TriggerZone[] = [];
  private insideIds: Set<string>   = new Set();
  private eKey:      Phaser.Input.Keyboard.Key;

  constructor(private scene: Phaser.Scene) {
    this.eKey = scene.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.E);
  }

  add(zone: TriggerZone): this { this.zones.push(zone); return this; }

  update(playerX: number, playerY: number): void {
    for (const zone of this.zones) {
      const inside = Phaser.Geom.Rectangle.Contains(zone.rect, playerX, playerY);

      if (zone.kind === 'proximity') {
        if (inside && !this.insideIds.has(zone.id)) {
          this.insideIds.add(zone.id);
          this.fireProximity(zone);
        } else if (!inside) {
          this.insideIds.delete(zone.id);
        }
      } else if (zone.kind === 'interact' && inside) {
        if (Phaser.Input.Keyboard.JustDown(this.eKey)) {
          this.fireInteract(zone);
        }
      }
    }
  }

  private fireProximity(zone: TriggerZone): void {
    if (zone.onTrigger) { zone.onTrigger(); return; }
    if ((zone.phase ?? 1) > 1) { this.showHint('即将开放'); return; }
    if (zone.type.startsWith('door_to')) {
      dispatch('cyber:door:approach', {
        targetScene:     zone.targetScene!,
        roomName:        zone.roomName!,
        modeDescription: zone.modeDescription ?? '',
      });
    }
  }

  private fireInteract(zone: TriggerZone): void {
    if (zone.onTrigger) { zone.onTrigger(); return; }
    if (zone.type === 'npc') {
      dispatch('cyber:npc:interact', { npcId: zone.npcId!, npcName: zone.npcName! });
    } else if (zone.type === 'object') {
      dispatch('cyber:object:interact', { objectId: zone.objectId!, contextHint: zone.contextHint });
    } else if (zone.type === 'examine') {
      dispatch('cyber:object:examine', {
        objectId: zone.objectId ?? zone.id,
        label:    zone.roomName ?? zone.id,
        query:    zone.examineQuery ?? '这里有什么？',
      });
    }
  }

  private showHint(msg: string): void {
    const { width, height } = this.scene.cameras.main;
    const t = this.scene.add.text(width / 2, height / 2 - 60, msg, {
      fontSize: '9px', color: '#f0a500', fontFamily: 'monospace',
      backgroundColor: '#161b22', padding: { x: 8, y: 5 },
    }).setOrigin(0.5).setDepth(10);
    this.scene.time.delayedCall(1800, () => t.destroy());
  }
}
