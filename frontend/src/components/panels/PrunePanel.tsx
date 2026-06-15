import { useState, useEffect } from 'react';
import { dispatch } from '../../eventbus';
import { getPruneCandidates, archiveNode, boostNode, type PruneStats, type PruneCandidate } from '../../api/client';
import './PrunePanel.css';

export function PrunePanel({ onBack }: { onBack: () => void }) {
  const [stats,      setStats]      = useState<PruneStats>({ critical: 0, warning: 0, healthy: 0 });
  const [candidates, setCandidates] = useState<PruneCandidate[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [boostingId, setBoostingId] = useState<string | null>(null);
  const [boostValue, setBoostValue] = useState('');

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'prune' });
    void getPruneCandidates()
      .then(data => { setStats(data.stats); setCandidates(data.candidates); })
      .finally(() => setLoading(false));
    return () => dispatch('cyber:panel:closed', { panelId: 'prune' });
  }, []);

  const handleArchive = async (id: string) => {
    await archiveNode(id, '');
    setCandidates(prev => prev.filter(c => c.node.id !== id));
  };

  const handleSkip = (id: string) => {
    setCandidates(prev => prev.filter(c => c.node.id !== id));
  };

  const handleBoostConfirm = async (id: string) => {
    const val = parseInt(boostValue, 10);
    if (isNaN(val) || val < 1 || val > 10) return;
    await boostNode(id, val);
    setCandidates(prev => prev.filter(c => c.node.id !== id));
    setBoostingId(null);
  };

  return (
    <div className="prune-panel">
      <div className="prune-header">
        <button className="btn-pixel" onClick={onBack} data-testid="prune-back">← 返回</button>
        <span className="prune-title">老化管理</span>
      </div>

      {!loading && (
        <div className="prune-stats-grid">
          <div className="prune-stat prune-stat--critical">
            <div className="prune-stat-count" data-testid="prune-critical">{stats.critical}</div>
            <div className="prune-stat-label">紧急</div>
          </div>
          <div className="prune-stat prune-stat--warning">
            <div className="prune-stat-count" data-testid="prune-warning">{stats.warning}</div>
            <div className="prune-stat-label">接近</div>
          </div>
          <div className="prune-stat prune-stat--healthy">
            <div className="prune-stat-count" data-testid="prune-healthy">{stats.healthy}</div>
            <div className="prune-stat-label">健康</div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="prune-loading">加载中…</div>
      ) : candidates.length === 0 ? (
        <div className="prune-empty">暂无需处理的老化节点 ✓</div>
      ) : (
        <div className="prune-candidate-list">
          {candidates.map(c => (
            <div
              key={c.node.id}
              className={`prune-candidate prune-candidate--${c.severity}`}
            >
              <div className="prune-candidate-info">
                <div className="prune-candidate-label">{c.node.label}</div>
                <div className="prune-candidate-meta">
                  <span>老化分 {c.stalenessScore.toFixed(1)}</span>
                  <span>·</span>
                  <span>重要度 {c.node.importance}</span>
                  <span>·</span>
                  <span className={`prune-severity prune-severity--${c.severity}`}>
                    {c.severity === 'critical' ? '紧急' : c.severity === 'warning' ? '接近' : '健康'}
                  </span>
                </div>
              </div>

              {boostingId === c.node.id ? (
                <div className="prune-boost-row">
                  <input
                    type="number" min={1} max={10}
                    value={boostValue}
                    onChange={e => setBoostValue(e.target.value)}
                    className="prune-boost-input"
                    data-testid={`prune-boost-input-${c.node.id}`}
                  />
                  <button
                    className="btn-pixel prune-boost-confirm"
                    onClick={() => void handleBoostConfirm(c.node.id)}
                    data-testid={`prune-boost-confirm-${c.node.id}`}
                  >确认</button>
                  <button
                    className="btn-pixel"
                    onClick={() => setBoostingId(null)}
                  >取消</button>
                </div>
              ) : (
                <div className="prune-candidate-actions">
                  <button
                    className="btn-pixel prune-btn-archive"
                    onClick={() => void handleArchive(c.node.id)}
                    data-testid={`prune-archive-${c.node.id}`}
                  >归档</button>
                  <button
                    className="btn-pixel prune-btn-boost"
                    onClick={() => { setBoostingId(c.node.id); setBoostValue(String(c.node.importance)); }}
                    data-testid={`prune-boost-${c.node.id}`}
                  >提升重要度</button>
                  <button
                    className="btn-pixel prune-btn-skip"
                    onClick={() => handleSkip(c.node.id)}
                    data-testid={`prune-skip-${c.node.id}`}
                  >跳过</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
