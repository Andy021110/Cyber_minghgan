import './WelcomePage.css';

export function WelcomePage({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="welcome-overlay">
      <div className="welcome-card">
        <div className="welcome-header">
          <div className="welcome-avatar">🤖</div>
          <div>
            <div className="welcome-name">明翰</div>
            <div className="welcome-tagline">赛博明翰 · 认知图谱空间</div>
          </div>
        </div>

        <div className="welcome-rooms">
          <div className="welcome-section-label">这里有什么</div>
          <ul className="welcome-room-list">
            <li>🏠 大厅 · 和明翰聊天</li>
            <li>🏋️ 健身房 · 健康与身体</li>
            <li>💼 办公室 · 工作模式（即将开放）</li>
            <li>📚 学习室 · 学习成长（即将开放）</li>
          </ul>
        </div>

        <button
          className="btn-pixel welcome-enter"
          onClick={onEnter}
          data-testid="welcome-enter"
        >
          ▶ 进入空间
        </button>
      </div>
    </div>
  );
}
