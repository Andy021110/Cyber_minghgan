/**
 * hud.js — HUD 顶部栏逻辑（F9）
 *
 * 监听事件：
 *   cyber:scene:changed      { sceneKey, roomName } → 更新房间名
 *   cyber:notification:badge { count }              → 显示/隐藏角标
 */

const _roomEl  = document.getElementById('hud-room');
const _badgeEl = document.getElementById('hud-badge');

window.addEventListener('cyber:scene:changed', (e) => {
  if (_roomEl) _roomEl.textContent = e.detail.roomName ?? '';
});

window.addEventListener('cyber:notification:badge', (e) => {
  const count = e.detail.count ?? 0;
  if (!_badgeEl) return;
  if (count > 0) {
    _badgeEl.textContent = count;
    _badgeEl.hidden = false;
  } else {
    _badgeEl.hidden = true;
  }
});
