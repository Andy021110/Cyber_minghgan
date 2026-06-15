import { useState, useEffect } from 'react';
import { dispatch } from '../../eventbus';
import { getReviewItems, getPruneCandidates } from '../../api/client';
import './TaskboardPanel.css';

export interface TaskboardPanelProps {
  onNavigate: (panel: 'review' | 'kg' | 'prune') => void;
  onClose:    () => void;
}

export function TaskboardPanel({ onNavigate, onClose }: TaskboardPanelProps) {
  const [reviewCount, setReviewCount] = useState(0);
  const [pruneCount,  setPruneCount]  = useState(0);
  const [loading,     setLoading]     = useState(true);

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'taskboard' });
    void load();
    return () => dispatch('cyber:panel:closed', { panelId: 'taskboard' });
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [items, prune] = await Promise.all([getReviewItems(), getPruneCandidates()]);
      setReviewCount(items.length);
      setPruneCount(prune.stats.critical + prune.stats.warning);
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  };

  const total = reviewCount + pruneCount;

  return (
    <div className="taskboard-overlay">
      <div className="taskboard-box">
        <div className="taskboard-title-bar">
          <span className="taskboard-title">📋 任务板</span>
          <button className="btn-pixel" onClick={onClose} data-testid="taskboard-close">×</button>
        </div>

        {loading ? (
          <div className="taskboard-loading">加载中…</div>
        ) : total === 0 ? (
          <div className="taskboard-empty" data-testid="taskboard-empty">
            所有任务已处理完毕 ✓
          </div>
        ) : (
          <div className="taskboard-items">
            {reviewCount > 0 && (
              <button
                className="taskboard-row taskboard-row--review"
                onClick={() => onNavigate('review')}
                data-testid="taskboard-review-row"
              >
                <span className="taskboard-badge taskboard-badge--red">{reviewCount}</span>
                <div className="taskboard-row-text">
                  <div className="taskboard-row-title">蓄水池待审批</div>
                  <div className="taskboard-row-desc">待人工决策的 AI 观察</div>
                </div>
              </button>
            )}
            {pruneCount > 0 && (
              <button
                className="taskboard-row taskboard-row--prune"
                onClick={() => onNavigate('prune')}
                data-testid="taskboard-prune-row"
              >
                <span className="taskboard-badge taskboard-badge--gray">{pruneCount}</span>
                <div className="taskboard-row-text">
                  <div className="taskboard-row-title">节点老化提醒</div>
                  <div className="taskboard-row-desc">进入老化阈值的节点</div>
                </div>
              </button>
            )}
            <button
              className="taskboard-row taskboard-row--kg"
              onClick={() => onNavigate('kg')}
              data-testid="taskboard-kg-row"
            >
              <span className="taskboard-badge taskboard-badge--neutral">📖</span>
              <div className="taskboard-row-text">
                <div className="taskboard-row-title">浏览认知图谱</div>
                <div className="taskboard-row-desc">查看 Id / Ego / Superego 节点</div>
              </div>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
