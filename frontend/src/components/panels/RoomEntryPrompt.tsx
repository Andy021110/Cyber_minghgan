import { useState, useEffect } from 'react';
import { listen, dispatch } from '../../eventbus';
import './RoomEntryPrompt.css';

export function RoomEntryPrompt() {
  const [visible,      setVisible]      = useState(false);
  const [roomName,     setRoomName]     = useState('');
  const [modeDesc,     setModeDesc]     = useState('');
  const [targetScene,  setTargetScene]  = useState('');

  useEffect(() => {
    const off = listen('cyber:door:approach', ({ targetScene, roomName, modeDescription }: { targetScene: string; roomName: string; modeDescription: string }) => {
      setTargetScene(targetScene);
      setRoomName(roomName);
      setModeDesc(modeDescription);
      setVisible(true);
      dispatch('cyber:panel:opened', { panelId: 'room-entry' });
    });
    return off;
  }, []);

  const handleConfirm = () => {
    setVisible(false);
    dispatch('cyber:door:confirmed', { targetScene });
    dispatch('cyber:panel:closed',   { panelId: 'room-entry' });
  };

  const handleCancel = () => {
    setVisible(false);
    dispatch('cyber:door:cancelled', {});
    dispatch('cyber:panel:closed',   { panelId: 'room-entry' });
  };

  if (!visible) return null;

  return (
    <div className="room-entry-overlay" data-testid="room-entry">
      <div className="room-entry-box">
        <div className="room-entry-title">进入 {roomName}</div>
        {modeDesc && <div className="room-entry-desc">{modeDesc}</div>}
        <div className="room-entry-actions">
          <button className="btn-pixel btn-confirm" onClick={handleConfirm} data-testid="room-entry-confirm">
            [Y] 进入
          </button>
          <button className="btn-pixel btn-cancel"  onClick={handleCancel}  data-testid="room-entry-cancel">
            [N] 返回
          </button>
        </div>
      </div>
    </div>
  );
}
