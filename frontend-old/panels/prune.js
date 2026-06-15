/**
 * panels/prune.js — /prune 老化管理面板（F7）
 *
 * 触发方式：window.openPrunePanel()（开发快捷键，正式触发待 Q11 解答）
 * 发送事件：cyber:panel:opened、cyber:panel:closed
 */

import { getPruneCandidates, archiveNode, boostNode } from '../client.js';

// ── severity 配置 ─────────────────────────────────────────────────

const SEVERITY_CFG = {
  critical: { label: '候选归档',  colorVar: '--color-id' },
  warning:  { label: '接近阈值',  colorVar: '--color-superego' },
  healthy:  { label: '健康',      colorVar: '--color-ego' },
};

// ── 面板状态 ──────────────────────────────────────────────────────

const _state = {
  open:          false,
  candidates:    [],  // 当前剩余未处理条目
  processedCount: 0,
};

// ── DOM 引用 ──────────────────────────────────────────────────────

let _panel, _closeBtn, _stats, _list;

// ── EventBus 工具 ─────────────────────────────────────────────────

function _dispatch(name, detail = {}) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

// ── 初始化 ────────────────────────────────────────────────────────

function _init() {
  const layer = document.getElementById('panel-layer');
  if (!layer) return;

  layer.insertAdjacentHTML('beforeend', `
    <div id="panel-prune" class="panel prune-panel" hidden>
      <div class="prune-header">
        <span class="prune-title">老化管理</span>
        <button class="panel__close" id="prune-close" aria-label="关闭">✕</button>
      </div>
      <div class="prune-stats" id="prune-stats"></div>
      <div class="prune-list"  id="prune-list"></div>
    </div>
  `);

  _panel    = document.getElementById('panel-prune');
  _closeBtn = document.getElementById('prune-close');
  _stats    = document.getElementById('prune-stats');
  _list     = document.getElementById('prune-list');

  _closeBtn.addEventListener('click', _close);

  // 开发快捷键（正式触发机制待 Q11 解答后补充）
  window.openPrunePanel = _open;
}

// ── 打开 ──────────────────────────────────────────────────────────

async function _open() {
  _state.open = true;
  _state.processedCount = 0;
  _panel.hidden = false;
  _dispatch('cyber:panel:opened', { panelId: 'prune' });
  window.addEventListener('keydown', _onKeydown);

  _stats.innerHTML = '<div class="prune-loading">加载中…</div>';
  _list.innerHTML  = '';

  try {
    const data = await getPruneCandidates();
    _renderStats(data.stats ?? {});
    _state.candidates = (data.candidates ?? []).slice(); // 本地副本，操作后移除
    _renderList();
  } catch {
    _stats.innerHTML = '<div class="prune-empty">加载失败</div>';
  }
}

// ── 关闭 ──────────────────────────────────────────────────────────

function _close() {
  if (!_state.open) return;
  _state.open = false;
  _panel.hidden = true;
  window.removeEventListener('keydown', _onKeydown);
  _dispatch('cyber:panel:closed', { panelId: 'prune' });
}

function _onKeydown(e) {
  if (e.key === 'Escape') _close();
}

// ── 渲染统计卡片 ──────────────────────────────────────────────────

function _renderStats(stats) {
  _stats.innerHTML = '';
  ['critical', 'warning', 'healthy'].forEach(key => {
    const cfg   = SEVERITY_CFG[key];
    const count = stats[key] ?? 0;
    const card  = document.createElement('div');
    card.className = 'prune-stat-card';
    card.innerHTML = `
      <span class="prune-stat-count" style="color:var(${cfg.colorVar})">${count}</span>
      <span class="prune-stat-label">${cfg.label}</span>
    `;
    _stats.appendChild(card);
  });
}

// ── 渲染候选列表 ──────────────────────────────────────────────────

function _renderList() {
  _list.innerHTML = '';

  if (_state.candidates.length === 0) {
    _list.innerHTML = `<div class="prune-empty">
      ${_state.processedCount > 0
        ? `本次处理 ${_state.processedCount} 条，全部完成`
        : '暂无需要处理的节点'}
    </div>`;
    return;
  }

  _state.candidates.forEach((candidate, idx) => {
    const row = _buildRow(candidate, idx);
    _list.appendChild(row);
  });
}

function _buildRow(candidate, idx) {
  const { node, stalenessScore, severity } = candidate;
  const cfg      = SEVERITY_CFG[severity] ?? SEVERITY_CFG.healthy;
  const score    = typeof stalenessScore === 'number'
    ? stalenessScore.toFixed(1)
    : '—';
  const created  = (node.createdAt ?? '').slice(0, 10);

  const row = document.createElement('div');
  row.className = 'prune-row';
  row.dataset.idx = idx;

  row.innerHTML = `
    <div class="prune-row-top">
      <span class="prune-severity-dot" style="background:var(${cfg.colorVar})"></span>
      <span class="prune-node-label">${node.label}</span>
      <span class="prune-score" style="color:var(${cfg.colorVar})">${score}</span>
    </div>
    <div class="prune-row-meta">
      <span>${node.layer} 层</span>
      <span>importance: ${node.importance}</span>
      <span>创建: ${created}</span>
    </div>
    <div class="prune-row-actions">
      <button class="prune-btn prune-btn--archive" data-idx="${idx}">归档</button>
      <button class="prune-btn prune-btn--boost"   data-idx="${idx}">提升重要度</button>
      <button class="prune-btn prune-btn--skip"    data-idx="${idx}">跳过</button>
    </div>
  `;

  row.querySelector('.prune-btn--archive').addEventListener('click', () => _onArchive(candidate, idx));
  row.querySelector('.prune-btn--boost').addEventListener('click',   () => _onBoost(candidate, idx));
  row.querySelector('.prune-btn--skip').addEventListener('click',    () => _onSkip(idx));

  return row;
}

// ── 操作处理 ──────────────────────────────────────────────────────

async function _onArchive(candidate, idx) {
  _disableRow(idx);
  await archiveNode(candidate.node.id, '').catch(() => {});
  _removeCandidate(idx);
}

async function _onBoost(candidate, idx) {
  _disableRow(idx);
  const newImp = Math.min((candidate.node.importance ?? 5) + 2, 10);
  await boostNode(candidate.node.id, newImp).catch(() => {});
  _removeCandidate(idx);
}

function _onSkip(idx) {
  // 跳过：只在本次会话中移除，不调用 API
  _removeCandidate(idx);
}

function _removeCandidate(idx) {
  _state.candidates.splice(idx, 1);
  _state.processedCount++;
  _renderList();
}

function _disableRow(idx) {
  const row = _list.querySelector(`[data-idx="${idx}"]`);
  if (row) row.querySelectorAll('button').forEach(b => { b.disabled = true; });
}

// ── 启动 ──────────────────────────────────────────────────────────

_init();
