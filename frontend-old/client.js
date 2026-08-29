/**
 * client.js — FastAPI 请求封装
 *
 * USE_MOCK = true  → 所有函数返回本地硬编码数据，不发网络请求
 * USE_MOCK = false → 调用真实 /api/* 端点
 *
 * F10 联调时将此开关改为 false。
 */

export const USE_MOCK = true;

// 注意：勿在此硬编码真实密钥（曾误提交明文密钥）。本地调试自行填入，切勿提交。
export const PRIVATE_KEY = '';
export const IS_PRIVATE_MODE = PRIVATE_KEY !== '';

const API_BASE = 'http://localhost:8000';


// ══════════════════════════════════════════════════════════════════
//  Mock 数据
// ══════════════════════════════════════════════════════════════════

const _MOCK_RESPONSE = '你好！我是赛博明翰，你的赛博分身。今天有什么想聊的吗？你的认知图谱正在持续更新中……';

const _MOCK_KG_NODES = [
  {
    id: 'aaaa0001bbbb0002cccc0003dddd0004',
    label: '高压下回避型应对',
    layer: 'Id',
    description: '在感知到外部压力时，倾向于拖延或转移注意力而非直面问题。',
    importance: 7,
    evidence: ['对话中多次提到"等等再说"', '周末将工作推到周一现象'],
    createdAt: '2026-05-01T10:00:00Z',
    lastAccessed: '2026-06-05T08:30:00Z',
    archived: false,
    archiveReason: null,
  },
  {
    id: 'eeee0005ffff0006aaaa0007bbbb0008',
    label: '深度工作偏好',
    layer: 'Ego',
    description: '在安静、无打扰的环境下工作效率显著更高，主动保护专注时段。',
    importance: 9,
    evidence: ['关闭通知偏好', '早晨 6-9 点产出质量最高'],
    createdAt: '2026-04-15T08:00:00Z',
    lastAccessed: '2026-06-07T20:00:00Z',
    archived: false,
    archiveReason: null,
  },
  {
    id: 'cccc0009dddd0010eeee0011ffff0012',
    label: '长期主义价值观',
    layer: 'Superego',
    description: '决策时优先考虑五年后的影响，即使短期代价更高也愿意接受。',
    importance: 8,
    evidence: ['多次拒绝短期高薪但低成长机会', '投资逻辑倾向复利'],
    createdAt: '2026-03-20T14:00:00Z',
    lastAccessed: '2026-05-10T12:00:00Z',
    archived: false,
    archiveReason: null,
  },
  {
    id: 'aaaa1111bbbb2222cccc3333dddd4444',
    label: '间歇性运动动力',
    layer: 'Ego',
    description: '运动习惯不稳定，外部触发（如天气、情绪）对是否锻炼影响很大。',
    importance: 5,
    evidence: ['健身记录显示间隔不规律'],
    createdAt: '2026-02-10T07:00:00Z',
    lastAccessed: '2026-04-01T09:00:00Z',
    archived: false,
    archiveReason: null,
  },
  {
    id: 'eeee5555ffff6666aaaa7777bbbb8888',
    label: '已归档：完美主义倾向',
    layer: 'Id',
    description: '过度关注细节导致交付延误。已通过刻意练习改善。',
    importance: 3,
    evidence: ['早期反刍日志'],
    createdAt: '2026-01-01T00:00:00Z',
    lastAccessed: '2026-02-01T00:00:00Z',
    archived: true,
    archiveReason: '行为模式已改变，不再适用',
  },
];

const _MOCK_REVIEW_ITEMS = [
  {
    id: 'review_001',
    pendingId: 'pending_001',
    timestamp: '2026-06-08T09:00:00Z',
    sourceMode: 'health',
    content: '用户连续三周忽略睡前运动提醒，优先选择刷手机',
    rawEvidence: '健康管家对话记录 2026-06-01 至 2026-06-08',
    proposedRoute: 'kg',
    proposedLayer: 'Id',
    aiRationale: '反映本能层面对即时刺激的偏好，属于 Id 层行为模式',
    importance: 6,
    importanceNote: '重复性强，但可干预，建议 6 分',
  },
  {
    id: 'review_002',
    pendingId: 'pending_002',
    timestamp: '2026-06-08T10:30:00Z',
    sourceMode: 'cyber',
    content: '本周目标完成率 80%，用户表示满意但希望提高',
    rawEvidence: '赛博明翰对话 2026-06-07',
    proposedRoute: 'log',
    proposedLayer: null,
    aiRationale: '属于周期性进度记录，不构成稳定行为模式，建议归 log',
    importance: null,
    importanceNote: null,
  },
];

const _MOCK_PRUNE_CANDIDATES = [
  {
    node: _MOCK_KG_NODES[3],
    stalenessScore: 38.4,
    severity: 'critical',
  },
  {
    node: _MOCK_KG_NODES[2],
    stalenessScore: 17.5,
    severity: 'warning',
  },
  {
    node: _MOCK_KG_NODES[0],
    stalenessScore: 4.7,
    severity: 'healthy',
  },
  {
    node: _MOCK_KG_NODES[1],
    stalenessScore: 0.1,
    severity: 'healthy',
  },
];

const _MOCK_NOTIFICATIONS = [
  {
    id: 'notif_001',
    timestamp: '2026-06-08T08:00:00Z',
    type: 'pending_ready',
    message: '有 2 条新的健康数据待审批',
  },
];


// ══════════════════════════════════════════════════════════════════
//  内部工具
// ══════════════════════════════════════════════════════════════════

/** 模拟 SSE 流式输出：逐字 yield，结束后触发 done / reflection。 */
async function _mockStream(text, onToken, onDone, onReflection) {
  const delay = (ms) => new Promise((r) => setTimeout(r, ms));
  for (const ch of text) {
    onToken(ch);
    await delay(25);
  }
  onDone(text);
  // mock 不触发反刍
  onReflection(false);
}

/** 解析 SSE 响应流，逐事件调用回调。 */
async function _readSSE(response, onToken, onDone, onReflection) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // 末尾不完整行留给下次拼接

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'token')      onToken(data.content);
        else if (data.type === 'done')  onDone(data.fullText);
        else if (data.type === 'reflection') onReflection(data.triggered);
      } catch {
        // 忽略非 JSON 行（如心跳）
      }
    }
  }
}


// ══════════════════════════════════════════════════════════════════
//  对话接口
// ══════════════════════════════════════════════════════════════════

/**
 * 向 NPC 发送消息，流式回调。
 *
 * @param {string}   npcId        NPC 标识符（见 TECH_SPEC 2.5）
 * @param {string}   message      用户消息
 * @param {Function} onToken      收到一个 token 时调用，参数为 string
 * @param {Function} onDone       流式完成时调用，参数为完整文本 string
 * @param {Function} onReflection 反刍结果回调，参数为 boolean
 * @param {string}  [contextHint] 可选，物件交互携带的上下文前缀（F3/GymScene 使用）
 *
 * 注：TECH_SPEC F2 原始签名为 chatStream(message, onToken, onDone, onReflection)，
 * 此处扩展为包含 npcId 和 contextHint，以满足 /api/chat 请求体要求和 F3 物件交互
 * 的上下文注入需求。签名变更已上报 Q9。
 */
export async function chatStream(npcId, message, onToken, onDone, onReflection, contextHint = null) {
  if (USE_MOCK) {
    await _mockStream(_MOCK_RESPONSE, onToken, onDone, onReflection);
    return;
  }

  const body = {
    npcId,
    message: contextHint ? `[${contextHint}]\n${message}` : message,
    privateKey: PRIVATE_KEY,
  };

  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  await _readSSE(response, onToken, onDone, onReflection);
}

/** 清空对话历史。 */
export async function clearChatHistory() {
  if (USE_MOCK) return { cleared: true };

  const res = await fetch(`${API_BASE}/api/chat/history`, { method: 'DELETE' });
  return res.json();
}


// ══════════════════════════════════════════════════════════════════
//  /review 审批接口
// ══════════════════════════════════════════════════════════════════

export async function getReviewItems() {
  if (USE_MOCK) return { items: _MOCK_REVIEW_ITEMS, count: _MOCK_REVIEW_ITEMS.length };

  const res = await fetch(`${API_BASE}/api/review/items`);
  return res.json();
}

export async function getReviewCount() {
  if (USE_MOCK) return { count: _MOCK_REVIEW_ITEMS.length };

  const res = await fetch(`${API_BASE}/api/review/count`);
  return res.json();
}

/**
 * @param {string}      itemId
 * @param {string}      decision    "approved_kg" | "approved_log" | "rejected"
 * @param {string}     [userNote]
 * @param {number|null}[importance]  1–10，仅 approved_kg 时有效
 * @param {string|null}[description] 仅 approved_kg 时有效
 */
export async function decideReviewItem(itemId, decision, userNote = '', importance = null, description = null, visibility = 'private') {
  if (USE_MOCK) return { success: true, itemId };

  const res = await fetch(`${API_BASE}/api/review/items/${itemId}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, userNote, importance, description, visibility }),
  });
  return res.json();
}


// ══════════════════════════════════════════════════════════════════
//  /kg 知识图谱接口
// ══════════════════════════════════════════════════════════════════

export async function getKgNodes(layer = null, includeArchived = false) {
  if (USE_MOCK) {
    let nodes = _MOCK_KG_NODES;
    if (!includeArchived) nodes = nodes.filter((n) => !n.archived);
    if (layer)            nodes = nodes.filter((n) => n.layer === layer);
    return { nodes, count: nodes.length };
  }

  const params = new URLSearchParams();
  if (layer)          params.set('layer', layer);
  if (includeArchived) params.set('includeArchived', 'true');

  const res = await fetch(`${API_BASE}/api/kg/nodes?${params}`);
  return res.json();
}

export async function getKgNode(nodeId) {
  if (USE_MOCK) {
    const node = _MOCK_KG_NODES.find((n) => n.id === nodeId) ?? null;
    return node;
  }

  const res = await fetch(`${API_BASE}/api/kg/nodes/${nodeId}`);
  if (res.status === 404) return null;
  return res.json();
}

export async function getKgGraph() {
  if (USE_MOCK) {
    const nodes = _MOCK_KG_NODES
      .filter((n) => !n.archived)
      .map(({ id, label, layer, importance }) => ({ id, label, layer, importance }));
    return { nodes, links: [] };
  }

  const res = await fetch(`${API_BASE}/api/kg/graph`);
  return res.json();
}


// ══════════════════════════════════════════════════════════════════
//  /prune 老化管理接口
// ══════════════════════════════════════════════════════════════════

export async function getPruneCandidates() {
  if (USE_MOCK) {
    const stats = { critical: 0, warning: 0, healthy: 0 };
    for (const c of _MOCK_PRUNE_CANDIDATES) stats[c.severity]++;
    return { stats, candidates: _MOCK_PRUNE_CANDIDATES };
  }

  const res = await fetch(`${API_BASE}/api/prune/candidates`);
  return res.json();
}

export async function archiveNode(nodeId, reason = '') {
  if (USE_MOCK) return { success: true };

  const res = await fetch(`${API_BASE}/api/prune/${nodeId}/archive`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  return res.json();
}

export async function boostNode(nodeId, newImportance) {
  if (USE_MOCK) return { success: true, newImportance };

  const res = await fetch(`${API_BASE}/api/prune/${nodeId}/boost`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ newImportance }),
  });
  return res.json();
}


// ══════════════════════════════════════════════════════════════════
//  /notifications 通知接口
// ══════════════════════════════════════════════════════════════════

export async function getNotifications() {
  if (USE_MOCK) return { notifications: _MOCK_NOTIFICATIONS, count: _MOCK_NOTIFICATIONS.length };

  const res = await fetch(`${API_BASE}/api/notifications`);
  return res.json();
}

export async function consumeNotification(notificationId) {
  if (USE_MOCK) return { success: true };

  const res = await fetch(`${API_BASE}/api/notifications/${notificationId}/consume`, {
    method: 'POST',
  });
  return res.json();
}
