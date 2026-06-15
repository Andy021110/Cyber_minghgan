import { useState, useEffect } from 'react';
import { dispatch } from '../../eventbus';
import { getKgNodes, type KGNode } from '../../api/client';
import './KGPanel.css';

type Tab = 'all' | 'Id' | 'Ego' | 'Superego' | 'archived';

const LAYER_COLOR: Record<string, string> = {
  Id:        'var(--color-id)',
  Ego:       'var(--color-ego)',
  Superego:  'var(--color-superego)',
};

const LAYER_HELP = `Id 层：本能驱动、情绪原始记录\nEgo 层：理性认知、行为模式\nSuperego 层：价值观、自我期望`;

export function KGPanel({ onBack }: { onBack: () => void }) {
  const [nodes,      setNodes]      = useState<KGNode[]>([]);
  const [activeTab,  setActiveTab]  = useState<Tab>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showHelp,   setShowHelp]   = useState(false);
  const [loading,    setLoading]    = useState(true);

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'kg' });
    void getKgNodes(undefined, true)
      .then(data => setNodes(data))
      .finally(() => setLoading(false));
    return () => dispatch('cyber:panel:closed', { panelId: 'kg' });
  }, []);

  const filtered = nodes.filter(n => {
    if (activeTab === 'archived') return n.archived;
    if (activeTab === 'all')      return !n.archived;
    return !n.archived && n.layer === activeTab;
  });

  const expanded = expandedId ? nodes.find(n => n.id === expandedId) : null;

  return (
    <div className="kg-panel">
      <div className="kg-header">
        <button className="btn-pixel kg-back" onClick={onBack} data-testid="kg-back">← 返回</button>
        <span className="kg-panel-title">认知图谱</span>
        <button
          className="btn-pixel kg-help-btn"
          onClick={() => setShowHelp(v => !v)}
          title="三层含义"
        >?</button>
      </div>

      {showHelp && (
        <div className="kg-help-card">
          {LAYER_HELP.split('\n').map(l => <div key={l}>{l}</div>)}
        </div>
      )}

      <div className="kg-tabs">
        {(['all', 'Id', 'Ego', 'Superego', 'archived'] as Tab[]).map(tab => (
          <button
            key={tab}
            className={`btn-pixel kg-tab${activeTab === tab ? ' kg-tab--active' : ''}`}
            onClick={() => { setActiveTab(tab); setExpandedId(null); }}
            data-testid={`tab-${tab}`}
            style={
              activeTab === tab && LAYER_COLOR[tab]
                ? { borderColor: LAYER_COLOR[tab], color: LAYER_COLOR[tab] }
                : undefined
            }
          >
            {tab === 'all' ? '全部' : tab === 'archived' ? '归档' : tab}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="kg-loading">加载中…</div>
      ) : filtered.length === 0 ? (
        <div className="kg-empty">暂无节点</div>
      ) : (
        <div className="kg-node-list">
          {filtered.map(node => (
            <button
              key={node.id}
              className={`kg-node-card${node.archived ? ' kg-node-card--archived' : ''}`}
              onClick={() => setExpandedId(id => id === node.id ? null : node.id)}
              data-testid={`kg-node-${node.id}`}
            >
              <div
                className="kg-node-color-bar"
                style={{ background: LAYER_COLOR[node.layer] ?? '#888' }}
              />
              <div className="kg-node-body">
                <div className="kg-node-top">
                  <span className="kg-node-label">{node.label}</span>
                  <span className="kg-node-importance">★ {node.importance}</span>
                </div>
                <div className="kg-node-layer-tag">{node.layer}</div>
                <div className="kg-node-desc">{node.description}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {expanded && (
        <div className="kg-expanded-overlay" data-testid="kg-expanded">
          <div className="kg-expanded-card">
            <div className="kg-expanded-header">
              <span
                className="kg-expanded-layer"
                style={{ color: LAYER_COLOR[expanded.layer] }}
              >{expanded.layer}</span>
              <span className="kg-expanded-title">{expanded.label}</span>
              <button
                className="btn-pixel"
                onClick={() => setExpandedId(null)}
              >×</button>
            </div>
            <div className="kg-expanded-desc">{expanded.description}</div>
            <div className="kg-expanded-meta">
              <span>重要度 {expanded.importance}</span>
              {expanded.archiveReason && <span>归档原因：{expanded.archiveReason}</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
