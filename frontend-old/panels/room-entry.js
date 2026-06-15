/**
 * panels/room-entry.js — 房间入口确认提示（F8）
 *
 * 监听事件：cyber:door:approach { targetScene, roomName, modeDescription }
 * 发送事件：
 *   按 Y → cyber:door:confirmed { targetScene }
 *          cyber:panel:closed  { panelId: "room-entry" }
 *   按 N / Esc → cyber:door:cancelled
 *                cyber:panel:closed  { panelId: "room-entry" }
 */

// ── 面板状态 ──────────────────────────────────────────────────────

const _state = {
  open:        false,
  targetScene: null,
};

// ── DOM 引用 ──────────────────────────────────────────────────────

let _panel, _roomName, _modeDesc, _btnY, _btnN;

// ── EventBus 工具 ─────────────────────────────────────────────────

function _dispatch(name, detail = {}) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

// ── 初始化 ────────────────────────────────────────────────────────

function _init() {
  const layer = document.getElementById('panel-layer');
  if (!layer) return;

  layer.insertAdjacentHTML('beforeend', `
    <div id="panel-room-entry" class="panel room-entry-panel" hidden>
      <div class="room-entry-room" id="room-entry-room"></div>
      <div class="room-entry-desc" id="room-entry-desc"></div>
      <div class="room-entry-btns">
        <button class="room-entry-btn room-entry-btn--yes" id="room-entry-yes">Y — 进入</button>
        <button class="room-entry-btn room-entry-btn--no"  id="room-entry-no">N — 取消</button>
      </div>
    </div>
  `);

  _panel    = document.getElementById('panel-room-entry');
  _roomName = document.getElementById('room-entry-room');
  _modeDesc = document.getElementById('room-entry-desc');
  _btnY     = document.getElementById('room-entry-yes');
  _btnN     = document.getElementById('room-entry-no');

  _btnY.addEventListener('click', _confirm);
  _btnN.addEventListener('click', _cancel);
}

// ── 打开 ──────────────────────────────────────────────────────────

function _open({ targetScene, roomName, modeDescription }) {
  _state.open        = true;
  _state.targetScene = targetScene;

  _roomName.textContent = roomName;
  _modeDesc.textContent = modeDescription;

  _panel.hidden = false;
  _dispatch('cyber:panel:opened', { panelId: 'room-entry' });
  window.addEventListener('keydown', _onKeydown);
  _btnY.focus();
}

// ── 确认进入 ──────────────────────────────────────────────────────

function _confirm() {
  if (!_state.open) return;
  const targetScene = _state.targetScene;
  _dispatch('cyber:door:confirmed', { targetScene });
  _close();
}

// ── 取消 ──────────────────────────────────────────────────────────

function _cancel() {
  if (!_state.open) return;
  _dispatch('cyber:door:cancelled');
  _close();
}

function _close() {
  _state.open        = false;
  _state.targetScene = null;
  _panel.hidden      = true;
  window.removeEventListener('keydown', _onKeydown);
  _dispatch('cyber:panel:closed', { panelId: 'room-entry' });
}

function _onKeydown(e) {
  if (e.key === 'Escape' || e.key === 'n' || e.key === 'N') _cancel();
  if (e.key === 'y' || e.key === 'Y') _confirm();
}

// ── EventBus 监听 ─────────────────────────────────────────────────

window.addEventListener('cyber:door:approach', (e) => {
  _open(e.detail);
});

// ── 启动 ──────────────────────────────────────────────────────────

_init();
