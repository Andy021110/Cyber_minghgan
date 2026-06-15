/**
 * panels/taskboard.js — /review 任务板面板（F4）
 *
 * 监听事件：cyber:object:interact { objectId: "taskboard" }
 * 发送事件：cyber:panel:opened、cyber:panel:closed
 *
 * 条目点击会调用 _reviewOpener(item)，由 F5 review.js 初始化后注册。
 */

import { getReviewItems, IS_PRIVATE_MODE } from '../client.js';

// ── 来源标签映射（TECH_SPEC 5.3）────────────────────────────────

const SOURCE_LABELS = {
  health: { text: '健身房', colorVar: '--color-id' },
  work:   { text: '办公室', colorVar: '--color-superego' },
  study:  { text: '学习室', colorVar: '--color-superego' },
  cyber:  { text: '赛博明翰', colorVar: '--color-ego' },
};

// ── F5 接入点（review.js 初始化后调用 setReviewOpener 注册）──────

let _reviewOpener = null;

export function setReviewOpener(fn) {
  _reviewOpener = fn;
}

// ── 面板状态 ──────────────────────────────────────────────────────

const _state = { open: false };

// ── DOM 引用 ──────────────────────────────────────────────────────

let _panel, _list, _closeBtn;

// ── EventBus 工具 ─────────────────────────────────────────────────

function _dispatch(name, detail = {}) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

// ── 初始化 ────────────────────────────────────────────────────────

function _init() {
  const layer = document.getElementById('panel-layer');
  if (!layer) return;

  layer.insertAdjacentHTML('beforeend', `
    <div id="panel-taskboard" class="panel taskboard-panel" hidden>
      <div class="taskboard-header">
        <span class="taskboard-title">待审批条目</span>
        <button class="panel__close" id="taskboard-close" aria-label="关闭">✕</button>
      </div>
      <div class="taskboard-list" id="taskboard-list"></div>
    </div>
  `);

  _panel    = document.getElementById('panel-taskboard');
  _list     = document.getElementById('taskboard-list');
  _closeBtn = document.getElementById('taskboard-close');

  _closeBtn.addEventListener('click', _close);
}

// ── 打开面板 ──────────────────────────────────────────────────────

async function _open() {
  if (!IS_PRIVATE_MODE) return;
  _state.open = true;
  _list.innerHTML = '<div class="taskboard-loading">加载中…</div>';
  _panel.hidden = false;
  _dispatch('cyber:panel:opened', { panelId: 'taskboard' });
  window.addEventListener('keydown', _onKeydown);

  try {
    const { items } = await getReviewItems();
    _renderList(items);
  } catch {
    _list.innerHTML = '<div class="taskboard-empty">加载失败，请重试</div>';
  }
}

// ── 关闭面板 ──────────────────────────────────────────────────────

function _close() {
  if (!_state.open) return;
  _state.open = false;
  _panel.hidden = true;
  _dispatch('cyber:panel:closed', { panelId: 'taskboard' });
  window.removeEventListener('keydown', _onKeydown);
}

function _onKeydown(e) {
  if (e.key === 'Escape') _close();
}

// ── 渲染条目列表 ──────────────────────────────────────────────────

function _renderList(items) {
  if (!items || items.length === 0) {
    _list.innerHTML = '<div class="taskboard-empty">暂无待审批条目</div>';
    return;
  }

  _list.innerHTML = '';
  items.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'taskboard-item';
    row.dataset.itemId = item.id;

    const src = SOURCE_LABELS[item.sourceMode] ?? { text: item.sourceMode, colorVar: '--color-text' };
    const preview = item.content.length > 60
      ? item.content.slice(0, 60) + '…'
      : item.content;
    const date = item.timestamp ? item.timestamp.slice(0, 10) : '';
    const route = item.proposedRoute === 'kg' ? '[→KG]' : '[→LOG]';

    row.innerHTML = `
      <span class="taskboard-tag" style="color:var(${src.colorVar})">${src.text}</span>
      <span class="taskboard-route">${route}</span>
      <span class="taskboard-preview">${preview}</span>
      <span class="taskboard-date">${date}</span>
    `;

    row.addEventListener('click', () => _onItemClick(item));
    _list.appendChild(row);
  });
}

function _onItemClick(item) {
  if (typeof _reviewOpener === 'function') {
    _close();
    _reviewOpener(item);
  }
  // F5 未加载时点击无响应，F5 init 后通过 setReviewOpener 注册
}

// ── EventBus 监听 ─────────────────────────────────────────────────

window.addEventListener('cyber:object:interact', (e) => {
  if (e.detail.objectId === 'taskboard') _open();
});

// ── 启动 ──────────────────────────────────────────────────────────

_init();
