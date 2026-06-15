import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
import { GAME_WIDTH, GAME_HEIGHT, GAME_ZOOM } from './config';
import { ROOM_CONFIG } from './roomConfig';

export function PhaserGame() {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef      = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;

    gameRef.current = new Phaser.Game({
      type:            Phaser.AUTO,
      width:           GAME_WIDTH,
      height:          GAME_HEIGHT,
      zoom:            GAME_ZOOM,
      pixelArt:        true,
      backgroundColor: '#0d1117',
      parent:          containerRef.current,
      physics: {
        default: 'arcade',
        arcade:  { gravity: { x: 0, y: 0 }, debug: false },
      },
      scene: ROOM_CONFIG.map(r => r.sceneClass),
    });

    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ position: 'fixed', inset: 0, zIndex: 0 }}
    />
  );
}
