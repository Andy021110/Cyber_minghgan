import { useState, useEffect } from 'react';
import { PhaserGame }       from './game/PhaserGame';
import { HUD }              from './components/HUD';
import { RoomEntryPrompt }  from './components/panels/RoomEntryPrompt';
import { DialoguePanel }    from './components/panels/DialoguePanel';
import { TaskboardPanel }   from './components/panels/TaskboardPanel';
import { ReviewPanel }      from './components/panels/ReviewPanel';
import { KGPanel }          from './components/panels/KGPanel';
import { PrunePanel }       from './components/panels/PrunePanel';
import { WelcomePage }      from './pages/WelcomePage';
import { useAuth }          from './contexts/AuthContext';
import { listen }           from './eventbus';
import './styles/tokens.css';
import './App.css';

type ActivePanel =
  | { id: 'dialogue'; npcId: string; npcName: string }
  | { id: 'taskboard' }
  | { id: 'review' }
  | { id: 'kg' }
  | { id: 'prune' }
  | null;

export default function App() {
  const { isOwner } = useAuth();
  const [entered,     setEntered]     = useState(isOwner);
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const [reflectionFlash, setReflectionFlash] = useState(false);
  const [examineQuery, setExamineQuery] = useState<string | undefined>(undefined);

  useEffect(() => {
    const offNpc = listen('cyber:npc:interact', ({ npcId, npcName }) => {
      setActivePanel({ id: 'dialogue', npcId, npcName });
    });
    const offObj = listen('cyber:object:interact', ({ objectId }) => {
      if (objectId === 'taskboard' && isOwner) setActivePanel({ id: 'taskboard' });
      if (objectId === 'kg'        && isOwner) setActivePanel({ id: 'kg' });
    });
    const offExamine = listen('cyber:object:examine', ({ query }) => {
      setExamineQuery(query);
      setActivePanel({ id: 'dialogue', npcId: 'cyber_minghan', npcName: '赛博明翰' });
    });
    return () => { offNpc(); offObj(); offExamine(); };
  }, [isOwner]);

  useEffect(() => {
    const offFlash = listen('cyber:reflection:triggered', () => {
      setReflectionFlash(true);
      setTimeout(() => setReflectionFlash(false), 2000);
    });
    return offFlash;
  }, []);

  if (!entered) {
    return <WelcomePage onEnter={() => setEntered(true)} />;
  }

  return (
    <>
      <div className={`game-wrapper${reflectionFlash ? ' game-wrapper--flash' : ''}`}>
        <PhaserGame />
      </div>
      <div id="panel-layer">
        <HUD />
        <RoomEntryPrompt />

        {activePanel?.id === 'dialogue' && (
          <DialoguePanel
            npcId={activePanel.npcId}
            npcName={activePanel.npcName}
            onClose={() => { setActivePanel(null); setExamineQuery(undefined); }}
            initialQuery={examineQuery}
          />
        )}

        {isOwner && activePanel?.id === 'taskboard' && (
          <TaskboardPanel
            onNavigate={(p) => setActivePanel({ id: p })}
            onClose={() => setActivePanel(null)}
          />
        )}

        {isOwner && activePanel?.id === 'review' && (
          <ReviewPanel onBack={() => setActivePanel({ id: 'taskboard' })} />
        )}

        {isOwner && activePanel?.id === 'kg' && (
          <KGPanel onBack={() => setActivePanel({ id: 'taskboard' })} />
        )}

        {isOwner && activePanel?.id === 'prune' && (
          <PrunePanel onBack={() => setActivePanel({ id: 'taskboard' })} />
        )}
      </div>
    </>
  );
}
