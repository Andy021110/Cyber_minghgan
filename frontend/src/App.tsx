import { PhaserGame }       from './game/PhaserGame';
import { HUD }              from './components/HUD';
import { RoomEntryPrompt }  from './components/panels/RoomEntryPrompt';
import './styles/tokens.css';
import './App.css';

export default function App() {
  return (
    <>
      {/* Layer 0: Phaser game world (fixed, z-index 0) */}
      <PhaserGame />

      {/* Layer 1: React panel overlay (z-index 100+) */}
      <div id="panel-layer">
        <HUD />
        <RoomEntryPrompt />
        {/* Plan 2 panels will be added here: DialoguePanel, TaskboardPanel, ReviewPanel, KGPanel, PrunePanel */}
      </div>
    </>
  );
}
