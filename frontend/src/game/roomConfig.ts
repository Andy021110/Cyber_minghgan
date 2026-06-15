import type Phaser from 'phaser';

export interface RoomConfig {
  key:        string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sceneClass: new (...args: any[]) => Phaser.Scene;
  label:      string;
  phase:      number;
}

// Scenes imported lazily to avoid circular deps; populated in main Phaser setup.
// roomConfig.ts is the canonical list — add Phase 2 rooms here only.
import { WorldScene }  from './scenes/WorldScene';
import { GymScene }    from './scenes/GymScene';
import { OfficeScene } from './scenes/OfficeScene';
import { StudyScene }  from './scenes/StudyScene';

export const ROOM_CONFIG: RoomConfig[] = [
  { key: 'WorldScene',  sceneClass: WorldScene,  label: '中央区', phase: 1 },
  { key: 'GymScene',    sceneClass: GymScene,    label: '健身房', phase: 1 },
  { key: 'OfficeScene', sceneClass: OfficeScene, label: '办公室', phase: 2 },
  { key: 'StudyScene',  sceneClass: StudyScene,  label: '学习室', phase: 2 },
];
