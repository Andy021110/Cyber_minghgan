/**
 * panels/dialogue.js — NPC 对话框面板（F3）
 *
 * 监听事件：cyber:npc:interact、cyber:object:interact
 * 发送事件：cyber:panel:opened、cyber:panel:closed
 */

import { chatStream } from '../client.js';

// ── NPC 显示配置 ──────────────────────────────────────────────────

const NPC_CONFIG = {
  cyber_minghan:   { name: '赛博明翰', colorVar: '--color-ego' },
  health_coach:    { name: '健康管家', colorVar: '--color-id' },
  work_assistant:  { name: '工作助手', colorVar: '--color-superego' },
  study_assistant: { name: '学习助手', colorVar: '--color-text' },
};

// 物件 → NPC 映射（cyber:object:interact 时用）
const OBJECT_TO_NPC = {
  weight_calendar: 'health_coach',
  training_log:    'health_coach',
};

// ── 面板状态 ──────────────────────────────────────────────────────

const _state = {
  open:             false,
  streaming:        false,
  npcId:            null,
  contextHint:      null,   // 仅首条消息携带，发送后清空
  reflectionTimer:  null,
  activeBubble:     null,   // 当前流式写入的 NPC 气泡 <div>
  cursorEl:         null,   // 光标 <span>
};

// ── DOM 引用（_init() 后有效）────────────────────────────────────

let _panel, _avatar, _npcName, _reflectionHint, _closeBtn,
    _messages, _input, _sendBtn;

// ── EventBus 工具 ─────────────────────────────────────────────────

function _dispatch(name, detail = {}) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

// ── 初始化：注入 DOM ──────────────────────────────────────────────

function _init() {
  const layer = document.getElementById('panel-layer');
  if (!layer) return;

  layer.insertAdjacentHTML('beforeend', `
    <div id="panel-dialogue" class="panel dialogue-panel" hidden>
      <div class="dialogue-header">
        <div class="dialogue-avatar" id="dialogue-avatar"></div>
        <span class="dialogue-npc-name" id="dialogue-npc-name"></span>
        <div class="dialogue-reflection" id="dialogue-reflection" hidden>💡 正在更新认知图谱…</div>
        <button class="panel__close" id="dialogue-close" aria-label="关闭">✕</button>
      </div>
      <div class="dialogue-messages" id="dialogue-messages"></div>
      <div class="dialogue-input-row">
        <input class="dialogue-input" id="dialogue-input"
               type="text" placeholder="说些什么…" autocomplete="off">
        <button class="dialogue-send" id="dialogue-send">发送</button>
      </div>
    </div>
  `);

  _panel          = document.getElementById('panel-dialogue');
  _avatar         = document.getElementById('dialogue-avatar');
  _npcName        = document.getElementById('dialogue-npc-name');
  _reflectionHint = document.getElementById('dialogue-reflection');
  _closeBtn       = document.getElementById('dialogue-close');
  _messages       = document.getElementById('dialogue-messages');
  _input          = document.getElementById('dialogue-input');
  _sendBtn        = document.getElementById('dialogue-send');

  _closeBtn.addEventListener('click', _close);
  _sendBtn.addEventListener('click', _send);
  _input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.isComposing) _send();
  });
}

// ── 打开面板 ──────────────────────────────────────────────────────

function _open(npcId, npcName, contextHint = null) {
  const config = NPC_CONFIG[npcId] ?? { name: npcName, colorVar: '--color-text' };

  _state.open        = true;
  _state.npcId       = npcId;
  _state.contextHint = contextHint;

  // 头像：颜色方块 + 首字
  _avatar.style.background = `var(${config.colorVar})`;
  _avatar.textContent = config.name[0];

  // NPC 名称（优先用 config，fallback 用事件里的 npcName）
  _npcName.textContent = config.name || npcName;

  // 清空上一次的消息记录
  _messages.innerHTML = '';
  _reflectionHint.hidden = true;

  _input.placeholder = `和${config.name}说些什么…`;
  _panel.hidden = false;
  _input.focus();

  _dispatch('cyber:panel:opened', { panelId: 'dialogue' });

  // 全局 Esc 监听
  window.addEventListener('keydown', _onKeydown);
}

// ── 关闭面板 ──────────────────────────────────────────────────────

function _close() {
  if (!_state.open) return;

  _state.open = false;
  _panel.hidden = true;

  if (_state.reflectionTimer) {
    clearTimeout(_state.reflectionTimer);
    _state.reflectionTimer = null;
  }

  _dispatch('cyber:panel:closed', { panelId: 'dialogue' });
  window.removeEventListener('keydown', _onKeydown);
}

function _onKeydown(e) {
  if (e.key === 'Escape') _close();
}

// ── 发送消息 ──────────────────────────────────────────────────────

async function _send() {
  const text = _input.value.trim();
  if (!text || _state.streaming) return;

  _input.value = '';

  // 用户气泡
  _appendBubble('user', text);

  // 消费一次 contextHint（仅首条消息携带）
  const hint = _state.contextHint;
  _state.contextHint = null;

  _setStreaming(true);

  // 准备空的 NPC 气泡
  _state.activeBubble = _appendBubble('npc', '');
  _state.cursorEl = document.createElement('span');
  _state.cursorEl.className = 'cursor';
  _state.cursorEl.textContent = '|';
  _state.activeBubble.appendChild(_state.cursorEl);

  await chatStream(
    _state.npcId,
    text,
    _onToken,
    _onDone,
    _onReflection,
    hint,
  );
}

// ── SSE 回调 ──────────────────────────────────────────────────────

function _onToken(token) {
  if (!_state.activeBubble || !_state.cursorEl) return;
  // 在光标前插入文本节点
  _state.activeBubble.insertBefore(
    document.createTextNode(token),
    _state.cursorEl,
  );
  _scrollToBottom();
}

function _onDone(_fullText) {
  if (_state.cursorEl) {
    _state.cursorEl.remove();
    _state.cursorEl = null;
  }
  _state.activeBubble = null;
  _setStreaming(false);
  _input.focus();
}

function _onReflection(triggered) {
  if (!triggered) return;
  _reflectionHint.hidden = false;
  if (_state.reflectionTimer) clearTimeout(_state.reflectionTimer);
  _state.reflectionTimer = setTimeout(() => {
    _reflectionHint.hidden = true;
    _state.reflectionTimer = null;
  }, 3000);
}

// ── DOM 工具 ──────────────────────────────────────────────────────

function _appendBubble(role, text) {
  const div = document.createElement('div');
  div.className = `dialogue-bubble dialogue-bubble--${role}`;
  div.textContent = text;
  _messages.appendChild(div);
  _scrollToBottom();
  return div;
}

function _scrollToBottom() {
  _messages.scrollTop = _messages.scrollHeight;
}

function _setStreaming(active) {
  _state.streaming     = active;
  _input.disabled      = active;
  _sendBtn.disabled    = active;
}

// ── EventBus 监听 ─────────────────────────────────────────────────

window.addEventListener('cyber:npc:interact', (e) => {
  const { npcId, npcName } = e.detail;
  _open(npcId, npcName);
});

window.addEventListener('cyber:object:interact', (e) => {
  const { objectId, contextHint } = e.detail;
  const targetNpcId = OBJECT_TO_NPC[objectId];
  if (!targetNpcId) return; // taskboard 等其他物件由各自面板处理
  const config = NPC_CONFIG[targetNpcId];
  _open(targetNpcId, config?.name ?? targetNpcId, contextHint ?? null);
});

// ── 启动 ──────────────────────────────────────────────────────────

_init();
