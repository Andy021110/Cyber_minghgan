import { WorldScene }  from './scenes/WorldScene.js';
import { GymScene }    from './scenes/GymScene.js';
import { OfficeScene } from './scenes/OfficeScene.js';
import { StudyScene }  from './scenes/StudyScene.js';

// 所有场景通过此数组注册；新增房间只需在此追加一行，不改 main.js
export const ROOM_CONFIG = [
  { key: 'WorldScene',  sceneClass: WorldScene,  label: '中央区', phase: 1 },
  { key: 'GymScene',    sceneClass: GymScene,    label: '健身房', phase: 1 },
  { key: 'OfficeScene', sceneClass: OfficeScene, label: '办公室', phase: 2 },
  { key: 'StudyScene',  sceneClass: StudyScene,  label: '学习室', phase: 2 },
];
