/**
 * panels/review.js — /review 逐条审批面板（F5）
 *
 * 由 taskboard.js 通过 setReviewOpener 调用打开。
 * 从 API 获取完整队列，从头逐条处理（不从 clicked item 开始，见 Q12）。
 * 发送事件：cyber:panel:opened / cyber:panel:closed / cyber:review:done
 */

import { getReviewItems, decideReviewItem } from '../client.js';
import { setReviewOpener } from './taskboard.js';

// ── 来源标签 ──────────────────────────────────────────────────────

const SOURCE_LABELS = {
  health: { text: '健身房', colorVar: '--color-id' },
  work:   { text: '办公室', colorVar: '--color-superego' },
  study:  { text: '学习室', colorVar: '--color-superego' },
  cyber:  { text: '赛博明翰', colorVar: '--color-ego' },
};

// ── 面板状态 ──────────────────────────────────────────────────────

const _state = {
  open:           false,
  items:          [],
  idx:            0,
  processedCount: 0,
};

// ── DOM 引用 ──────────────────────────────────────────────────────

let _panel, _progress, _closeBtn,
    _sourceTag, _routeTag, _layerTag,
    _content, _evidence, _rationale,
    _kgSection, _importanceRange, _importanceVal, _descInput,
    _btnY, _btnN, _btnS, _btnQ;

// ── EventBus 工具 ─────────────────────────────────────────────────

function _dispatch(name, detail = {}) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

// ── 初始化 ────────────────────────────────────────────────────────

function _init() {
  const layer = document.getElementById('panel-layer');
  if (!layer) return;

  layer.insertAdjacentHTML('beforeend', `
    <div id="panel-review" class="panel review-panel" hidden>

      <div class="review-header">
        <span class="review-progress" id="review-progress">审批条目</span>
        <button class="panel__close" id="review-close" aria-label="关闭">✕</button>
      </div>

      <div class="review-meta">
        <span class="review-source-tag" id="review-source-tag"></span>
        <span class="review-route-tag" id="review-route-tag"></span>
        <span class="review-layer-tag" id="review-layer-tag"></span>
      </div>

      <div class="review-body">
        <div class="review-field">
          <span class="review-label">观察内容</span>
          <div class="review-content" id="review-content"></div>
        </div>
        <div class="review-field">
          <span class="review-label">原始证据</span>
          <div class="review-evidence" id="review-evidence"></div>
        </div>
        <div class="review-field">
          <span class="review-label">AI 分类理由</span>
          <div class="review-rationale" id="review-rationale"></div>
        </div>
      </div>

      <div class="review-kg-section" id="review-kg-section" hidden>
        <div class="review-field">
          <span class="review-label">重要度
            <span class="review-importance-val" id="review-importance-val">5</span>/10
          </span>
          <input class="review-slider" id="review-importance"
                 type="range" min="1" max="10" value="5">
        </div>
        <div class="review-field">
          <span class="review-label">节点描述</span>
          <textarea class="review-desc" id="review-desc" rows="2"
                    placeholder="留空则使用观察内容作为描述"></textarea>
        </div>
        <div class="review-field">
          <span class="review-label">可见性</span>
          <label style="margin-right:12px">
            <input type="radio" name="review-visibility" value="private" checked> 私有
          </label>
          <label>
            <input type="radio" name="review-visibility" value="public"> 公开
          </label>
        </div>
      </div>

      <div class="review-actions">
        <button class="review-btn review-btn--y" id="review-btn-y">Y 采纳</button>
        <button class="review-btn review-btn--n" id="review-btn-n">N 拒绝</button>
        <button class="review-btn review-btn--s" id="review-btn-s">S 跳过</button>
        <button class="review-btn review-btn--q" id="review-btn-q">Q 暂停</button>
      </div>

    </div>
  `);

  _panel         = document.getElementById('panel-review');
  _progress      = document.getElementById('review-progress');
  _closeBtn      = document.getElementById('review-close');
  _sourceTag     = document.getElementById('review-source-tag');
  _routeTag      = document.getElementById('review-route-tag');
  _layerTag      = document.getElementById('review-layer-tag');
  _content       = document.getElementById('review-content');
  _evidence      = document.getElementById('review-evidence');
  _rationale     = document.getElementById('review-rationale');
  _kgSection     = document.getElementById('review-kg-section');
  _importanceRange = document.getElementById('review-importance');
  _importanceVal = document.getElementById('review-importance-val');
  _descInput     = document.getElementById('review-desc');
  _btnY          = document.getElementById('review-btn-y');
  _btnN          = document.getElementById('review-btn-n');
  _btnS          = document.getElementById('review-btn-s');
  _btnQ          = document.getElementById('review-btn-q');

  _importanceRange.addEventListener('input', () => {
    _importanceVal.textContent = _importanceRange.value;
  });

  _closeBtn.addEventListener('click', _quit);
  _btnY.addEventListener('click', _approve);
  _btnN.addEventListener('click', _reject);
  _btnS.addEventListener('click', _skip);
  _btnQ.addEventListener('click', _quit);

  // 向 taskboard 注册打开函数
  setReviewOpener(_openFromTaskboard);
}

// ── 打开 ──────────────────────────────────────────────────────────

async function _openFromTaskboard(_startItem) {
  // 始终从队列头开始处理（见 Q12）
  _state.processedCount = 0;
  _state.idx = 0;

  _panel.hidden = false;
  _state.open = true;
  _dispatch('cyber:panel:opened', { panelId: 'review' });
  window.addEventListener('keydown', _onKeydown);

  _progress.textContent = '加载中…';
  try {
    const { items } = await getReviewItems();
    _state.items = items ?? [];
  } catch {
    _state.items = [];
  }

  if (_state.items.length === 0) {
    _showEmpty();
  } else {
    _renderItem();
  }
}

// ── 渲染当前条目 ──────────────────────────────────────────────────

function _renderItem() {
  const item = _state.items[_state.idx];
  const total = _state.items.length;

  _progress.textContent = `审批条目 [${_state.idx + 1}/${total}]`;

  const src = SOURCE_LABELS[item.sourceMode] ?? { text: item.sourceMode, colorVar: '--color-text' };
  _sourceTag.textContent = src.text;
  _sourceTag.style.color = `var(${src.colorVar})`;

  const isKg = item.proposedRoute === 'kg';
  _routeTag.textContent = isKg ? '→ KG 图谱' : '→ health_log';
  _routeTag.style.color = isKg ? 'var(--color-ego)' : 'var(--color-text)';

  _layerTag.textContent = item.proposedLayer ? `${item.proposedLayer} 层` : '';
  _layerTag.hidden = !item.proposedLayer;

  _content.textContent  = item.content   || '—';
  _evidence.textContent = item.rawEvidence || '—';
  _rationale.textContent = item.aiRationale || '—';

  // KG 专属字段
  _kgSection.hidden = !isKg;
  if (isKg) {
    const imp = item.importance ?? 5;
    _importanceRange.value = imp;
    _importanceVal.textContent = imp;
    const note = item.importanceNote ? `  (${item.importanceNote})` : '';
    _descInput.placeholder = `留空则使用观察内容${note}`;
    _descInput.value = '';
    const privateRadio = document.querySelector('input[name="review-visibility"][value="private"]');
    if (privateRadio) privateRadio.checked = true;
  }
}

function _showEmpty() {
  _progress.textContent = '暂无待审批条目';
  _sourceTag.textContent = '';
  _routeTag.textContent = '';
  _layerTag.hidden = true;
  _content.textContent = '';
  _evidence.textContent = '';
  _rationale.textContent = '';
  _kgSection.hidden = true;
  [_btnY, _btnN, _btnS].forEach(b => { b.disabled = true; });
}

// ── 操作处理 ──────────────────────────────────────────────────────

async function _approve() {
  const item = _state.items[_state.idx];
  if (!item) return;

  const isKg       = item.proposedRoute === 'kg';
  const decision   = isKg ? 'approved_kg' : 'approved_log';
  const importance = isKg ? parseInt(_importanceRange.value, 10) : null;
  const desc       = isKg ? (_descInput.value.trim() || null) : null;
  const visibility = isKg
    ? (document.querySelector('input[name="review-visibility"]:checked')?.value ?? 'private')
    : 'private';

  _setDisabled(true);
  await decideReviewItem(item.id, decision, '', importance, desc, visibility).catch(() => {});
  _state.processedCount++;
  _advance();
}

async function _reject() {
  const item = _state.items[_state.idx];
  if (!item) return;

  _setDisabled(true);
  await decideReviewItem(item.id, 'rejected', '', null, null).catch(() => {});
  _state.processedCount++;
  _advance();
}

function _skip() {
  _advance();
}

function _quit() {
  _close(true);
}

function _advance() {
  _state.idx++;
  _setDisabled(false);
  if (_state.idx >= _state.items.length) {
    _finishAll();
  } else {
    _renderItem();
  }
}

function _finishAll() {
  const count = _state.processedCount;
  _progress.textContent = `完成！本次处理 ${count} 条`;
  _content.textContent = '';
  _evidence.textContent = '';
  _rationale.textContent = '';
  _kgSection.hidden = true;
  _setDisabled(true);
  _dispatch('cyber:review:done', { processedCount: count });
  setTimeout(() => _close(false), 1500);
}

function _close(byUser = false) {
  if (!_state.open) return;
  _state.open = false;
  _panel.hidden = true;
  [_btnY, _btnN, _btnS].forEach(b => { b.disabled = false; });
  window.removeEventListener('keydown', _onKeydown);
  _dispatch('cyber:panel:closed', { panelId: 'review' });
}

function _setDisabled(v) {
  [_btnY, _btnN, _btnS, _btnQ].forEach(b => { b.disabled = v; });
  _importanceRange.disabled = v;
  _descInput.disabled = v;
  document.querySelectorAll('input[name="review-visibility"]').forEach(r => { r.disabled = v; });
}

// ── 键盘快捷键 ────────────────────────────────────────────────────

function _onKeydown(e) {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  switch (e.key.toLowerCase()) {
    case 'y': _approve(); break;
    case 'n': _reject();  break;
    case 's': _skip();    break;
    case 'q': case 'escape': _quit(); break;
  }
}

// ── 启动 ──────────────────────────────────────────────────────────

_init();
