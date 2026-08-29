const BASE = 'http://localhost:8000/api';

// ── Types ─────────────────────────────────────────────────────────

export interface ReviewItem {
  id:             string;
  pendingId:      string;
  timestamp:      string;
  sourceMode:     string;
  content:        string;
  rawEvidence:    string;
  proposedRoute:  string;
  proposedLayer:  string | null;
  aiRationale:    string;
  importance:     number | null;
  importanceNote: string | null;
}

export interface KGNode {
  id:            string;
  label:         string;
  layer:         'Id' | 'Ego' | 'Superego';
  description:   string;
  importance:    number;
  evidence:      string[];
  createdAt:     string | null;
  lastAccessed:  string | null;
  archived:      boolean;
  archiveReason: string | null;
}

export interface PruneStats { critical: number; warning: number; healthy: number; }

export interface PruneCandidate {
  node:           KGNode;
  stalenessScore: number;
  severity:       'critical' | 'warning' | 'healthy';
}

export interface DecideRequest {
  decision:    'approved_kg' | 'approved_log' | 'rejected';
  userNote?:   string;
  importance?: number;
  description?: string;
}

// ── Review ───────────────────────────────────────────────────────

export async function getReviewCount(): Promise<number> {
  const res = await fetch(`${BASE}/review/count`);
  if (!res.ok) throw new Error('review/count failed');
  return ((await res.json()) as { count: number }).count;
}

export async function getReviewItems(): Promise<ReviewItem[]> {
  const res = await fetch(`${BASE}/review/items`);
  if (!res.ok) throw new Error('review/items failed');
  return ((await res.json()) as { items: ReviewItem[] }).items;
}

export async function decideReviewItem(itemId: string, req: DecideRequest): Promise<void> {
  const res = await fetch(`${BASE}/review/items/${itemId}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error('review decide failed');
}

// ── KG ───────────────────────────────────────────────────────────

export async function getKgNodes(layer?: string, includeArchived = false): Promise<KGNode[]> {
  const p = new URLSearchParams();
  if (layer) p.set('layer', layer);
  p.set('includeArchived', String(includeArchived));
  const res = await fetch(`${BASE}/kg/nodes?${p}`);
  if (!res.ok) throw new Error('kg/nodes failed');
  return ((await res.json()) as { nodes: KGNode[] }).nodes;
}

export async function getKgNode(nodeId: string): Promise<KGNode> {
  const res = await fetch(`${BASE}/kg/nodes/${nodeId}`);
  if (!res.ok) throw new Error(`kg/nodes/${nodeId} failed`);
  return res.json() as Promise<KGNode>;
}

// ── Prune ────────────────────────────────────────────────────────

export async function getPruneCandidates(): Promise<{ stats: PruneStats; candidates: PruneCandidate[] }> {
  const res = await fetch(`${BASE}/prune/candidates`);
  if (!res.ok) throw new Error('prune/candidates failed');
  return res.json() as Promise<{ stats: PruneStats; candidates: PruneCandidate[] }>;
}

export async function archiveNode(nodeId: string, reason = ''): Promise<void> {
  const res = await fetch(`${BASE}/prune/${nodeId}/archive`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error('prune archive failed');
}

export async function boostNode(nodeId: string, newImportance: number): Promise<void> {
  const res = await fetch(`${BASE}/prune/${nodeId}/boost`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ newImportance }),
  });
  if (!res.ok) throw new Error('prune boost failed');
}

// ── Chat (SSE streaming) ─────────────────────────────────────────

export function chatStream(
  npcId: string,
  message: string,
  privateKey: string,
  onToken: (token: string) => void,
  onDone: (fullText: string) => void,
  onReflection: (triggered: boolean, feature: string | null) => void,
  onTool?: (label: string) => void,
  onKGUpdate?: (nodeId: string, label: string) => void,
  onError?: (message: string) => void,
): () => void {
  let cancelled = false;

  void (async () => {
    let res: Response;
    try {
      res = await fetch(`${BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ npcId, message, privateKey }),
      });
    } catch (err) {
      // 原实现是 `catch { return; }`：后端不可达时静默无反应，
      // 用户会以为"功能没做出来"。这里必须把错误暴露出去。
      onError?.(
        `无法连接后端 ${BASE}（${
          err instanceof Error ? err.message : String(err)
        }）。请确认 uvicorn 已在 8000 端口启动。`,
      );
      return;
    }
    if (!res.ok) {
      onError?.(`后端返回 ${res.status} ${res.statusText || ''}`.trim());
      return;
    }
    if (!res.body) {
      onError?.('后端未返回响应流（SSE 未建立）');
      return;
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (!cancelled) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const evt = JSON.parse(line.slice(6)) as { type: string; content?: string; fullText?: string; triggered?: boolean; label?: string; feature?: string | null; nodeId?: string };
          if (evt.type === 'token' && evt.content)     onToken(evt.content);
          if (evt.type === 'done'  && evt.fullText)    onDone(evt.fullText);
          if (evt.type === 'reflection')               onReflection(evt.triggered ?? false, evt.feature ?? null);
          if (evt.type === 'tool'  && evt.label)       onTool?.(evt.label);
          if (evt.type === 'kg_update' && evt.nodeId)  onKGUpdate?.(evt.nodeId, evt.label ?? '');
        } catch { /* malformed chunk */ }
      }
    }
  })();

  return () => { cancelled = true; };
}

// ── Notifications ────────────────────────────────────────────────

export async function getNotificationCount(): Promise<number> {
  const res = await fetch(`${BASE}/notifications`);
  if (!res.ok) return 0;
  return ((await res.json()) as { count: number }).count;
}
