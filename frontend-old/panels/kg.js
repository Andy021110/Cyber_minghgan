/**
 * panels/kg.js — /kg 知识图谱面板（F6）
 *
 * 触发方式：window.openKgPanel()（开发快捷键 K，正式触发待 Q11 解答）
 * 发送事件：cyber:panel:opened、cyber:panel:closed
 */

import { getKgNodes } from '../client.js';

// ── importance 色标 ───────────────────────────────────────────────

function _importanceColor(imp) {
  if (imp >= 9) return 'var(--color-id)';
  if (imp >= 7) return 'var(--color-superego)';
  if (imp >= 4) return 'var(--color-text)';
  return 'var(--color-border)';
}

// ── 层级配置 ──────────────────────────────────────────────────────

const LAYERS = [
  { key: 'Id',       label: 'Id 层',       colorVar: '--color-id' },
  { key: 'Ego',      label: 'Ego 层',      colorVar: '--color-ego' },
  { key: 'Superego', label: 'Superego 层', colorVar: '--color-superego' },
];

// ── 面板状态 ──────────────────────────────────────────────────────

const _state = {
  open:           false,
  showArchived:   false,
  expandedNodeId: null,
  allNodes:       [],
};

// ── DOM 引用 ──────────────────────────────────────────────────────

let _panel, _closeBtn, _archivedToggle, _columns;

// ── EventBus 工具 ─────────────────────────────────────────────────

function _dispatch(name, detail = {}) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

// ── 初始化 ────────────────────────────────────────────────────────

function _init() {
  const layer = document.getElementById('panel-layer');
  if (!layer) return;

  layer.insertAdjacentHTML('beforeend', `
    <div id="panel-kg" class="panel kg-panel" hidden>
      <div class="kg-header">
        <span class="kg-title">知识图谱</span>
        <label class="kg-archive-toggle">
          <input type="checkbox" id="kg-archived-toggle"> 显示已归档
        </label>
        <button class="panel__close" id="kg-close" aria-label="关闭">✕</button>
      </div>
      <div class="kg-columns" id="kg-columns">
        ${LAYERS.map(l => `
          <div class="kg-column" id="kg-col-${l.key}">
            <div class="kg-col-header" style="color:var(${l.colorVar})">${l.label}</div>
            <div class="kg-col-nodes" id="kg-nodes-${l.key}"></div>
          </div>
        `).join('')}
      </div>
    </div>
  `);

  _panel          = document.getElementById('panel-kg');
  _closeBtn       = document.getElementById('kg-close');
  _archivedToggle = document.getElementById('kg-archived-toggle');
  _columns        = document.getElementById('kg-columns');

  _closeBtn.addEventListener('click', _close);
  _archivedToggle.addEventListener('change', () => {
    _state.showArchived = _archivedToggle.checked;
    _renderNodes();
  });

  // 开发快捷键（正式触发机制待 Q11 解答后补充）
  window.openKgPanel = _open;
}

// ── 打开 ──────────────────────────────────────────────────────────

async function _open() {
  _state.open = true;
  _state.expandedNodeId = null;
  _panel.hidden = false;
  _dispatch('cyber:panel:opened', { panelId: 'kg' });
  window.addEventListener('keydown', _onKeydown);

  // 清空并显示加载状态
  LAYERS.forEach(l => {
    document.getElementById(`kg-nodes-${l.key}`).innerHTML =
      '<div class="kg-loading">加载中…</div>';
  });

  try {
    const { nodes } = await getKgNodes(null, true); // 拉取含已归档
    _state.allNodes = nodes ?? [];
    _renderNodes();
  } catch {
    LAYERS.forEach(l => {
      document.getElementById(`kg-nodes-${l.key}`).innerHTML =
        '<div class="kg-empty">加载失败</div>';
    });
  }
}

// ── 关闭 ──────────────────────────────────────────────────────────

function _close() {
  if (!_state.open) return;
  _state.open = false;
  _panel.hidden = true;
  window.removeEventListener('keydown', _onKeydown);
  _dispatch('cyber:panel:closed', { panelId: 'kg' });
}

function _onKeydown(e) {
  if (e.key === 'Escape') _close();
}

// ── 渲染节点 ──────────────────────────────────────────────────────

function _renderNodes() {
  LAYERS.forEach(({ key }) => {
    const container = document.getElementById(`kg-nodes-${key}`);
    const nodes = _state.allNodes.filter(n => {
      if (n.layer !== key) return false;
      if (!_state.showArchived && n.archived) return false;
      return true;
    });

    if (nodes.length === 0) {
      container.innerHTML = '<div class="kg-empty">暂无节点</div>';
      return;
    }

    container.innerHTML = '';
    nodes.forEach(node => {
      const card = _buildCard(node);
      container.appendChild(card);
    });
  });
}

function _buildCard(node) {
  const card = document.createElement('div');
  card.className = 'kg-card' + (node.archived ? ' kg-card--archived' : '');
  card.dataset.nodeId = node.id;

  const impColor = _importanceColor(node.importance);
  const descPreview = node.description.length > 60
    ? node.description.slice(0, 60) + '…'
    : node.description;

  card.innerHTML = `
    <div class="kg-card-header">
      <span class="kg-card-dot" style="background:${impColor}"></span>
      <span class="kg-card-label">${node.label}</span>
      <span class="kg-card-imp" style="color:${impColor}">${node.importance}</span>
    </div>
    <div class="kg-card-desc">${descPreview}</div>
    <div class="kg-card-evidence" hidden></div>
  `;

  card.addEventListener('click', () => _toggleExpand(card, node));
  return card;
}

function _toggleExpand(card, node) {
  const evDiv = card.querySelector('.kg-card-evidence');
  const isOpen = !evDiv.hidden;

  // 折叠所有其他已展开的卡片
  _columns.querySelectorAll('.kg-card-evidence').forEach(el => {
    el.hidden = true;
  });

  if (isOpen) {
    _state.expandedNodeId = null;
    return;
  }

  _state.expandedNodeId = node.id;
  evDiv.hidden = false;

  if (evDiv.childElementCount === 0) {
    const fullDesc = document.createElement('div');
    fullDesc.className = 'kg-card-full-desc';
    fullDesc.textContent = node.description;
    evDiv.appendChild(fullDesc);

    if (node.evidence && node.evidence.length > 0) {
      const evTitle = document.createElement('div');
      evTitle.className = 'kg-card-ev-title';
      evTitle.textContent = '原始证据';
      evDiv.appendChild(evTitle);

      node.evidence.forEach(ev => {
        const p = document.createElement('div');
        p.className = 'kg-card-ev-item';
        p.textContent = ev;
        evDiv.appendChild(p);
      });
    }

    if (node.archiveReason) {
      const ar = document.createElement('div');
      ar.className = 'kg-card-archive-reason';
      ar.textContent = `归档原因：${node.archiveReason}`;
      evDiv.appendChild(ar);
    }
  }
}

// ── 启动 ──────────────────────────────────────────────────────────

_init();
