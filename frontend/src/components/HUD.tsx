import { useState, useEffect } from 'react';
import { listen, dispatch } from '../eventbus';
import { useAuth } from '../contexts/AuthContext';
import './HUD.css';

export function HUD() {
  const { isOwner } = useAuth();
  const [roomName,   setRoomName]   = useState('中央活动区');
  const [badgeCount, setBadgeCount] = useState(0);

  useEffect(() => {
    const off1 = listen('cyber:scene:changed',      ({ roomName }) => setRoomName(roomName));
    const off2 = listen('cyber:notification:badge', ({ count })   => setBadgeCount(count));
    return () => { off1(); off2(); };
  }, []);

  if (isOwner) {
    return (
      <div className="hud hud--owner" data-testid="hud">
        <span className="hud-room">🏠 {roomName}</span>
        <div className="hud-right">
          <button
            className="hud-btn hud-taskboard"
            onClick={() => dispatch('cyber:object:interact', { objectId: 'taskboard' })}
            data-testid="hud-taskboard-btn"
          >
            📋 任务板
            {badgeCount > 0 && (
              <span className="hud-badge" data-testid="hud-badge">{badgeCount}</span>
            )}
          </button>
          <button className="hud-btn hud-settings">⚙</button>
        </div>
      </div>
    );
  }

  return (
    <div className="hud hud--visitor" data-testid="hud">
      <span className="hud-indicator">👤 明翰的空间</span>
      <span className="hud-room">🏠 {roomName}</span>
      <button
        className="hud-btn hud-chat"
        onClick={() => dispatch('cyber:npc:interact', { npcId: 'cyber_minghan', npcName: '赛博明翰' })}
        data-testid="hud-chat-btn"
      >
        💬 和明翰聊天
      </button>
    </div>
  );
}
