import { useState, useEffect } from 'react';
import { dispatch } from '../../eventbus';
import { getReviewItems, decideReviewItem, type ReviewItem } from '../../api/client';
import './ReviewPanel.css';

export function ReviewPanel({ onBack }: { onBack: () => void }) {
  const [items,      setItems]      = useState<ReviewItem[]>([]);
  const [index,      setIndex]      = useState(0);
  const [decision,   setDecision]   = useState<'approved_kg' | 'rejected' | 'approved_log' | null>(null);
  const [userNote,   setUserNote]   = useState('');
  const [description, setDescription] = useState('');
  const [importance, setImportance] = useState(7);
  const [loading,    setLoading]    = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [done,       setDone]       = useState(false);

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'review' });
    const load = async () => {
      setLoading(true);
      try {
        const data = await getReviewItems();
        setItems(data);
        if (data.length > 0) {
          setDescription(data[0].content);
          setImportance(data[0].importance ?? 7);
        } else {
          setDone(true);
        }
      } finally { setLoading(false); }
    };
    void load();
    return () => dispatch('cyber:panel:closed', { panelId: 'review' });
  }, []);

  const currentItem = items[index];
  const showDescription = decision === null || decision === 'approved_kg';

  const selectDecision = (d: 'approved_kg' | 'rejected' | 'approved_log') => {
    setDecision(d);
  };

  const handleSubmit = async () => {
    if (!currentItem || !decision) return;
    setSubmitting(true);
    try {
      await decideReviewItem(currentItem.id, {
        decision,
        userNote:    userNote || undefined,
        importance:  decision === 'approved_kg' ? importance  : undefined,
        description: decision === 'approved_kg' ? description : undefined,
      });
      dispatch('cyber:review:done', { processedCount: 1 });
      advance();
    } finally { setSubmitting(false); }
  };

  const handleSkip = () => { advance(); };

  const advance = () => {
    const next = index + 1;
    if (next >= items.length) {
      setDone(true);
    } else {
      setIndex(next);
      setDecision(null);
      setUserNote('');
      setDescription(items[next].content);
      setImportance(items[next].importance ?? 7);
    }
  };

  if (loading) {
    return (
      <div className="review-panel">
        <div className="review-loading">加载中…</div>
      </div>
    );
  }

  if (done || !currentItem) {
    return (
      <div className="review-panel">
        <div className="review-empty" data-testid="review-empty">
          <div>所有审批项已处理完毕 ✓</div>
          <button className="btn-pixel" onClick={onBack} data-testid="review-back">← 返回</button>
        </div>
      </div>
    );
  }

  return (
    <div className="review-panel">
      <div className="review-header">
        <button className="btn-pixel review-back-btn" onClick={onBack} data-testid="review-back">
          ← 返回
        </button>
        <span className="review-progress">{index + 1} / {items.length}</span>
        <span className="review-source-tag">{currentItem.sourceMode}</span>
      </div>

      <div className="review-body">
        <div className="review-card" data-testid="review-content">
          {currentItem.content}
        </div>

        <div className="review-ai-hint">
          <span>AI 建议：{currentItem.proposedRoute === 'approved_kg' ? '写入图谱' : '只记日志'}</span>
          {currentItem.proposedLayer && (
            <span className={`review-layer-tag review-layer-tag--${currentItem.proposedLayer.toLowerCase()}`}>
              {currentItem.proposedLayer}
            </span>
          )}
          {currentItem.importance != null && (
            <span className="review-ai-importance">重要度 {currentItem.importance}</span>
          )}
        </div>

        <textarea
          className="review-user-note"
          value={userNote}
          onChange={e => setUserNote(e.target.value)}
          placeholder="你的看法或纠正（可选）"
          rows={2}
          data-testid="review-user-note"
        />

        {showDescription && (
          <div className="review-description-block" data-testid="review-description-block">
            <div className="review-label">写入图谱的描述</div>
            <textarea
              className="review-description-input"
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={3}
              data-testid="review-description"
            />
            <div className="review-importance-row">
              <span className="review-label">重要度</span>
              <input
                type="range" min={1} max={10}
                value={importance}
                onChange={e => setImportance(Number(e.target.value))}
                className="review-importance-slider"
                data-testid="review-importance-slider"
              />
              <span className="review-importance-value" data-testid="review-importance-value">
                {importance}
              </span>
            </div>
          </div>
        )}

        <div className="review-actions">
          <button
            className={`btn-pixel review-btn review-btn--y${decision === 'approved_kg' ? ' review-btn--selected' : ''}`}
            onClick={() => selectDecision('approved_kg')}
            data-testid="review-btn-y"
          >Y 写入图谱</button>
          <button
            className={`btn-pixel review-btn review-btn--n${decision === 'rejected' ? ' review-btn--selected' : ''}`}
            onClick={() => selectDecision('rejected')}
            data-testid="review-btn-n"
          >N 拒绝</button>
          <button
            className={`btn-pixel review-btn review-btn--s${decision === 'approved_log' ? ' review-btn--selected' : ''}`}
            onClick={() => selectDecision('approved_log')}
            data-testid="review-btn-s"
          >S 记日志</button>
          <button
            className="btn-pixel review-btn review-btn--q"
            onClick={handleSkip}
            data-testid="review-btn-q"
          >Q 跳过</button>
        </div>

        {decision !== null && (
          <button
            className="btn-pixel review-submit"
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="review-submit"
          >
            {submitting ? '提交中…' : '提交'}
          </button>
        )}
      </div>
    </div>
  );
}
