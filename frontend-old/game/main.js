// Phaser is loaded via <script> CDN tag in index.html before this module.
import { ROOM_CONFIG } from './roomConfig.js';

const config = {
  type: Phaser.AUTO,
  width: 720,
  height: 450,
  zoom: 2,
  pixelArt: true,
  backgroundColor: '#0d1117',
  parent: 'game-container',
  physics: {
    default: 'arcade',
    arcade: { gravity: { y: 0 }, debug: false },
  },
  scene: ROOM_CONFIG.map(r => r.sceneClass),
};

window.addEventListener('DOMContentLoaded', () => {
  new Phaser.Game(config);
});
