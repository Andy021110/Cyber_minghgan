# Frontend Plan 2 — All Functional Panels

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build all six functional panels (WelcomePage, DialoguePanel, TaskboardPanel, ReviewPanel, KGPanel, PrunePanel) and wire them into App.tsx.

**Architecture:** App.tsx lifts panel state into a discriminated union `ActivePanel` and listens to EventBus events to show/hide panels. Owner-only panels (Taskboard/Review/KG/Prune) are gated with `isOwner`. DialoguePanel dispatches `cyber:panel:opened/closed` internally on mount/unmount to pause/resume player movement. Visitors see WelcomePage before entering the game world.

**Tech Stack:** React 18, TypeScript 5, Vite 5, vitest + @testing-library/react, existing `frontend/src/api/client.ts`, existing `frontend/src/eventbus.ts`, existing `frontend/src/contexts/AuthContext.tsx`, CSS design tokens from `frontend/src/styles/tokens.css`.

---

## File Map

| Path | Action | Purpose |
|------|--------|---------|
| `frontend/src/pages/WelcomePage.tsx` | Create | Visitor entry card shown before game |
| `frontend/src/pages/WelcomePage.css` | Create | Styles for visitor card |
| `frontend/src/pages/WelcomePage.test.tsx` | Create | 3 unit tests |
| `frontend/src/components/panels/DialoguePanel.tsx` | Create | RPG bottom bar — NPC chat with SSE streaming |
| `frontend/src/components/panels/DialoguePanel.css` | Create | Styles for dialogue bar and expanded history |
| `frontend/src/components/panels/DialoguePanel.test.tsx` | Create | 7 unit tests |
| `frontend/src/components/panels/TaskboardPanel.tsx` | Create | Pending items summary (review + prune) |
| `frontend/src/components/panels/TaskboardPanel.css` | Create | Styles for task list overlay |
| `frontend/src/components/panels/TaskboardPanel.test.tsx` | Create | 5 unit tests |
| `frontend/src/components/panels/ReviewPanel.tsx` | Create | Y/N/S/Q approval flow |
| `frontend/src/components/panels/ReviewPanel.css` | Create | Styles for approval UI |
| `frontend/src/components/panels/ReviewPanel.test.tsx` | Create | 6 unit tests |
| `frontend/src/components/panels/KGPanel.tsx` | Create | Knowledge graph node browser with tabs |
| `frontend/src/components/panels/KGPanel.css` | Create | Styles for node cards and tabs |
| `frontend/src/components/panels/KGPanel.test.tsx` | Create | 5 unit tests |
| `frontend/src/components/panels/PrunePanel.tsx` | Create | Node aging management (archive/boost/skip) |
| `frontend/src/components/panels/PrunePanel.css` | Create | Styles for prune UI |
| `frontend/src/components/panels/PrunePanel.test.tsx` | Create | 5 unit tests |
| `frontend/src/App.tsx` | Modify | Add panel state, EventBus listeners, conditional rendering |
| `frontend/src/App.css` | Modify | Add pointer-events for new panels |
| `frontend/src/App.test.tsx` | Create | 3 integration tests |

---

### Task 1: WelcomePage

**Files:**
- Create: `frontend/src/pages/WelcomePage.tsx`
- Create: `frontend/src/pages/WelcomePage.css`
- Create: `frontend/src/pages/WelcomePage.test.tsx`

Context: Shown only to visitors (`isOwner === false`) before they enter the game world. Renders a "business card" style panel with room list and an entry button. Owns no state beyond what's passed in. Owner users skip this page entirely (handled in App.tsx Task 7).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/WelcomePage.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { WelcomePage } from './WelcomePage';

describe('WelcomePage', () => {
  it('renders name and tagline', () => {
    render(<WelcomePage onEnter={vi.fn()} />);
    expect(screen.getByText('明翰')).toBeInTheDocument();
    expect(screen.getByText(/赛博明翰/)).toBeInTheDocument();
  });

  it('renders all 4 rooms', () => {
    render(<WelcomePage onEnter={vi.fn()} />);
    expect(screen.getByText(/大厅/)).toBeInTheDocument();
    expect(screen.getByText(/健身房/)).toBeInTheDocument();
    expect(screen.getByText(/办公室/)).toBeInTheDocument();
    expect(screen.getByText(/学习室/)).toBeInTheDocument();
  });

  it('calls onEnter when button clicked', () => {
    const onEnter = vi.fn();
    render(<WelcomePage onEnter={onEnter} />);
    fireEvent.click(screen.getByTestId('welcome-enter'));
    expect(onEnter).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/pages/WelcomePage.test.tsx
```
Expected: error — `Cannot find module './WelcomePage'`

- [ ] **Step 3: Create WelcomePage.tsx**

Create `frontend/src/pages/WelcomePage.tsx`:

```tsx
import './WelcomePage.css';

export function WelcomePage({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="welcome-overlay">
      <div className="welcome-card">
        <div className="welcome-header">
          <div className="welcome-avatar">🤖</div>
          <div>
            <div className="welcome-name">明翰</div>
            <div className="welcome-tagline">赛博明翰 · 认知图谱空间</div>
          </div>
        </div>

        <div className="welcome-rooms">
          <div className="welcome-section-label">这里有什么</div>
          <ul className="welcome-room-list">
            <li>🏠 大厅 · 和赛博明翰聊天</li>
            <li>🏋️ 健身房 · 健康与身体</li>
            <li>💼 办公室 · 工作模式（即将开放）</li>
            <li>📚 学习室 · 学习成长（即将开放）</li>
          </ul>
        </div>

        <button
          className="btn-pixel welcome-enter"
          onClick={onEnter}
          data-testid="welcome-enter"
        >
          ▶ 进入空间
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create WelcomePage.css**

Create `frontend/src/pages/WelcomePage.css`:

```css
.welcome-overlay {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--game-bg);
}

.welcome-card {
  background: var(--panel-bg);
  border: var(--border-width) solid var(--panel-border);
  box-shadow: var(--pixel-shadow);
  padding: 24px 32px;
  width: 320px;
  font-family: var(--font-mono);
}

.welcome-header {
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 2px solid var(--panel-border);
  padding-bottom: 12px;
  margin-bottom: 12px;
}

.welcome-avatar { font-size: 32px; line-height: 1; }

.welcome-name {
  font-size: 14px;
  font-weight: bold;
  color: var(--panel-text);
}

.welcome-tagline {
  font-size: 8px;
  color: var(--panel-text-dim);
  margin-top: 4px;
}

.welcome-rooms { margin-bottom: 20px; }

.welcome-section-label {
  font-size: 8px;
  color: var(--panel-text-dim);
  margin-bottom: 8px;
}

.welcome-room-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.welcome-room-list li {
  font-size: 9px;
  color: var(--panel-text);
  padding: 4px 8px;
  background: var(--panel-bg-card);
  border-left: 3px solid var(--panel-border);
}

.welcome-enter {
  width: 100%;
  font-size: 10px;
  padding: 8px 0;
  background: var(--panel-title-bg);
  color: var(--panel-gold);
  border-color: var(--panel-shadow);
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/pages/WelcomePage.test.tsx
```
Expected: PASS — 3 tests

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/pages/WelcomePage.tsx src/pages/WelcomePage.css src/pages/WelcomePage.test.tsx
git commit -m "feat: add WelcomePage visitor entry card"
```

---

### Task 2: DialoguePanel

**Files:**
- Create: `frontend/src/components/panels/DialoguePanel.tsx`
- Create: `frontend/src/components/panels/DialoguePanel.css`
- Create: `frontend/src/components/panels/DialoguePanel.test.tsx`

Context: RPG-style bottom bar that opens when the player interacts with an NPC. Receives `npcId`, `npcName`, and `onClose` as props from App.tsx. On mount, dispatches `cyber:panel:opened` to pause player movement; on unmount (cleanup), dispatches `cyber:panel:closed` to resume. Calls `chatStream` from `api/client.ts` with SSE callbacks. Supports history expand/collapse.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/panels/DialoguePanel.test.tsx`:

```tsx
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DialoguePanel } from './DialoguePanel';
import { AuthContext, type AuthContextValue } from '../../contexts/AuthContext';

const { mockDispatch, mockChatStream } = vi.hoisted(() => ({
  mockDispatch: vi.fn(),
  mockChatStream: vi.fn(),
}));

vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client',  () => ({ chatStream: mockChatStream }));

const wrap = (isOwner = false) =>
  render(
    <AuthContext.Provider value={{ isOwner, privateKey: 'test-key' } satisfies AuthContextValue}>
      <DialoguePanel npcId="cyber_minghan" npcName="赛博明翰" onClose={vi.fn()} />
    </AuthContext.Provider>,
  );

describe('DialoguePanel', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('dispatches panel:opened on mount', () => {
    wrap();
    expect(mockDispatch).toHaveBeenCalledWith('cyber:panel:opened', { panelId: 'dialogue' });
  });

  it('dispatches panel:closed on unmount', () => {
    const { unmount } = wrap();
    unmount();
    expect(mockDispatch).toHaveBeenCalledWith('cyber:panel:closed', { panelId: 'dialogue' });
  });

  it('shows NPC name', () => {
    wrap();
    expect(screen.getByText('赛博明翰')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(
      <AuthContext.Provider value={{ isOwner: false, privateKey: '' } satisfies AuthContextValue}>
        <DialoguePanel npcId="cyber_minghan" npcName="赛博明翰" onClose={onClose} />
      </AuthContext.Provider>,
    );
    fireEvent.click(screen.getByTestId('dialogue-close'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows streaming text while chatStream is active', async () => {
    let capturedOnToken: ((t: string) => void) | undefined;
    mockChatStream.mockImplementation(
      (_npcId: string, _msg: string, _pk: string, onToken: (t: string) => void) => {
        capturedOnToken = onToken;
        return vi.fn();
      },
    );
    wrap();
    fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '你好' } });
    fireEvent.click(screen.getByTestId('dialogue-send'));
    await act(async () => { capturedOnToken?.('你好'); });
    expect(screen.getByTestId('dialogue-streaming')).toBeInTheDocument();
  });

  it('clears streaming element after onDone fires', async () => {
    let capturedOnDone: ((t: string) => void) | undefined;
    mockChatStream.mockImplementation(
      (_npcId: string, _msg: string, _pk: string, _onToken: (t: string) => void, onDone: (t: string) => void) => {
        capturedOnDone = onDone;
        return vi.fn();
      },
    );
    wrap();
    fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '你好' } });
    fireEvent.click(screen.getByTestId('dialogue-send'));
    await act(async () => { capturedOnDone?.('你好，世界'); });
    expect(screen.queryByTestId('dialogue-streaming')).toBeNull();
  });

  it('toggles history panel on expand button click', () => {
    wrap();
    expect(screen.queryByTestId('dialogue-history')).toBeNull();
    fireEvent.click(screen.getByTestId('dialogue-expand-btn'));
    expect(screen.getByTestId('dialogue-history')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('dialogue-expand-btn'));
    expect(screen.queryByTestId('dialogue-history')).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/panels/DialoguePanel.test.tsx
```
Expected: error — `Cannot find module './DialoguePanel'`

- [ ] **Step 3: Create DialoguePanel.tsx**

Create `frontend/src/components/panels/DialoguePanel.tsx`:

```tsx
import { useState, useEffect, useRef } from 'react';
import { dispatch } from '../../eventbus';
import { useAuth } from '../../contexts/AuthContext';
import { chatStream } from '../../api/client';
import './DialoguePanel.css';

interface Message {
  id:           string;
  role:         'user' | 'npc';
  text:         string;
  timestamp:    string;
  isReflection: boolean;
}

export interface DialoguePanelProps {
  npcId:   string;
  npcName: string;
  onClose: () => void;
}

export function DialoguePanel({ npcId, npcName, onClose }: DialoguePanelProps) {
  const { privateKey } = useAuth();
  const [messages,  setMessages]  = useState<Message[]>([]);
  const [streaming, setStreaming]  = useState('');
  const [input,     setInput]     = useState('');
  const [expanded,  setExpanded]  = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [lastReflection, setLastReflection] = useState(false);
  const cancelRef  = useRef<(() => void) | null>(null);
  const historyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'dialogue' });
    return () => {
      cancelRef.current?.();
      dispatch('cyber:panel:closed', { panelId: 'dialogue' });
    };
  }, []);

  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight;
    }
  }, [messages, streaming]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput('');
    setIsSending(true);
    setStreaming('');
    setLastReflection(false);

    const userMsg: Message = {
      id:           Date.now().toString(),
      role:         'user',
      text,
      timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
      isReflection: false,
    };
    setMessages(prev => [...prev, userMsg]);

    cancelRef.current = chatStream(
      npcId, text, privateKey,
      (token)    => setStreaming(prev => prev + token),
      (fullText) => {
        setStreaming('');
        setIsSending(false);
        setMessages(prev => [...prev, {
          id:           Date.now().toString(),
          role:         'npc',
          text:         fullText,
          timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
          isReflection: lastReflection,
        }]);
      },
      (triggered) => setLastReflection(triggered),
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const latestNpcMsg = [...messages].reverse().find(m => m.role === 'npc');

  return (
    <div className={`dialogue-panel${expanded ? ' dialogue-panel--expanded' : ''}`}>
      {expanded && (
        <div className="dialogue-history" ref={historyRef} data-testid="dialogue-history">
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`dialogue-msg dialogue-msg--${msg.role}${msg.isReflection ? ' dialogue-msg--reflection' : ''}`}
            >
              <div className="dialogue-msg-text">
                {msg.isReflection && <span className="dialogue-reflection-badge">💡 </span>}
                {msg.text}
              </div>
              <div className="dialogue-msg-time">{msg.timestamp}</div>
            </div>
          ))}
        </div>
      )}

      <div className="dialogue-bar">
        <div className="dialogue-bar-left">
          <div className="dialogue-npc-sprite">👤</div>
          <div className="dialogue-npc-name">{npcName}</div>
        </div>

        <div className="dialogue-bar-main">
          <div className="dialogue-current">
            {isSending ? (
              <>
                <span data-testid="dialogue-streaming">{streaming}</span>
                <span className="dialogue-cursor">▌</span>
              </>
            ) : latestNpcMsg ? (
              <span className={latestNpcMsg.isReflection ? 'dialogue-reflection-msg' : ''}>
                {latestNpcMsg.isReflection && <span className="dialogue-reflection-badge">💡 </span>}
                {latestNpcMsg.text}
              </span>
            ) : (
              <span className="dialogue-placeholder">按 Enter 发送消息…</span>
            )}
          </div>

          <div className="dialogue-input-row">
            <input
              className="dialogue-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息…"
              disabled={isSending}
              data-testid="dialogue-input"
            />
            <button
              className="btn-pixel dialogue-send"
              onClick={sendMessage}
              disabled={isSending || !input.trim()}
              data-testid="dialogue-send"
            >
              发送
            </button>
          </div>
        </div>

        <div className="dialogue-bar-right">
          <button
            className="btn-pixel dialogue-expand-btn"
            onClick={() => setExpanded(e => !e)}
            data-testid="dialogue-expand-btn"
          >
            {expanded ? '↓ 收起' : '↑ 历史'}
          </button>
          <button
            className="btn-pixel dialogue-close"
            onClick={onClose}
            data-testid="dialogue-close"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create DialoguePanel.css**

Create `frontend/src/components/panels/DialoguePanel.css`:

```css
.dialogue-panel {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 300;
  background: rgba(44, 22, 8, 0.97);
  border-top: var(--border-width) solid var(--panel-border);
  box-shadow: 0 -4px 0 var(--panel-shadow);
  font-family: var(--font-mono);
}

.dialogue-history {
  max-height: 35vh;
  overflow-y: auto;
  padding: 12px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-bottom: 2px solid var(--panel-border);
}

.dialogue-msg {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 80%;
}
.dialogue-msg--user { align-self: flex-end; }
.dialogue-msg--npc  { align-self: flex-start; }

.dialogue-msg-text {
  font-size: 10px;
  color: var(--panel-gold);
  background: var(--panel-title-bg);
  border: 1px solid var(--panel-border);
  padding: 4px 8px;
  line-height: 1.6;
}
.dialogue-msg--user .dialogue-msg-text {
  background: var(--panel-mid-bg);
  color: var(--panel-text);
}
.dialogue-msg--reflection .dialogue-msg-text {
  border-color: var(--panel-gold);
  box-shadow: 0 0 0 1px var(--panel-gold);
}

.dialogue-msg-time {
  font-size: 7px;
  color: var(--panel-text-dim);
  align-self: flex-end;
}

.dialogue-reflection-badge { color: var(--panel-gold); }

.dialogue-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  min-height: 80px;
}

.dialogue-bar-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 64px;
}
.dialogue-npc-sprite {
  font-size: 40px;
  line-height: 1;
}
.dialogue-npc-name {
  font-size: 8px;
  color: var(--panel-gold);
  text-align: center;
  max-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dialogue-bar-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dialogue-current {
  font-size: 10px;
  color: var(--panel-gold);
  min-height: 20px;
  line-height: 1.6;
}
.dialogue-placeholder { color: var(--panel-text-dim); }

@keyframes blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}
.dialogue-cursor {
  animation: blink 0.125s step-end infinite; /* ~8fps */
  color: var(--panel-gold);
}

.dialogue-input-row {
  display: flex;
  gap: 8px;
}
.dialogue-input {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 10px;
  background: var(--panel-bg-card);
  color: var(--panel-text);
  border: var(--border-width) solid var(--panel-border);
  padding: 4px 8px;
}
.dialogue-input:disabled { opacity: 0.5; }

.dialogue-bar-right {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-end;
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/panels/DialoguePanel.test.tsx
```
Expected: PASS — 7 tests

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/components/panels/DialoguePanel.tsx src/components/panels/DialoguePanel.css src/components/panels/DialoguePanel.test.tsx
git commit -m "feat: add DialoguePanel with SSE streaming and history expand"
```

---

### Task 3: TaskboardPanel

**Files:**
- Create: `frontend/src/components/panels/TaskboardPanel.tsx`
- Create: `frontend/src/components/panels/TaskboardPanel.css`
- Create: `frontend/src/components/panels/TaskboardPanel.test.tsx`

Context: Full-screen overlay shown to owner when they interact with the taskboard object or click the HUD taskboard button. Fetches review item count and prune candidate counts on mount, shows colored badge rows, calls `onNavigate` to open the corresponding detail panel.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/panels/TaskboardPanel.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TaskboardPanel } from './TaskboardPanel';
import { getReviewItems, getPruneCandidates } from '../../api/client';

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client', () => ({
  getReviewItems: vi.fn(),
  getPruneCandidates: vi.fn(),
}));

const REVIEW_ITEM = {
  id: '1', pendingId: 'p1', timestamp: '', sourceMode: 'gym',
  content: 'test', rawEvidence: '', proposedRoute: 'approved_kg',
  proposedLayer: 'Ego', aiRationale: '', importance: 7, importanceNote: '',
};
const PRUNE_RESULT = { stats: { critical: 2, warning: 3, healthy: 10 }, candidates: [] };

describe('TaskboardPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getReviewItems).mockResolvedValue([REVIEW_ITEM]);
    vi.mocked(getPruneCandidates).mockResolvedValue(PRUNE_RESULT);
  });

  it('dispatches panel:opened on mount', () => {
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    expect(mockDispatch).toHaveBeenCalledWith('cyber:panel:opened', { panelId: 'taskboard' });
  });

  it('shows review item row after loading', async () => {
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('taskboard-review-row')).toBeInTheDocument());
    expect(screen.getByTestId('taskboard-review-row')).toHaveTextContent('1');
  });

  it('shows prune row with critical+warning count', async () => {
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('taskboard-prune-row')).toBeInTheDocument());
    expect(screen.getByTestId('taskboard-prune-row')).toHaveTextContent('5');
  });

  it('calls onNavigate("review") when review row clicked', async () => {
    const onNavigate = vi.fn();
    render(<TaskboardPanel onNavigate={onNavigate} onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('taskboard-review-row'));
    fireEvent.click(screen.getByTestId('taskboard-review-row'));
    expect(onNavigate).toHaveBeenCalledWith('review');
  });

  it('shows empty state when all counts are zero', async () => {
    vi.mocked(getReviewItems).mockResolvedValueOnce([]);
    vi.mocked(getPruneCandidates).mockResolvedValueOnce({ stats: { critical: 0, warning: 0, healthy: 5 }, candidates: [] });
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('taskboard-empty')).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/panels/TaskboardPanel.test.tsx
```
Expected: error — `Cannot find module './TaskboardPanel'`

- [ ] **Step 3: Create TaskboardPanel.tsx**

Create `frontend/src/components/panels/TaskboardPanel.tsx`:

```tsx
import { useState, useEffect } from 'react';
import { dispatch } from '../../eventbus';
import { getReviewItems, getPruneCandidates } from '../../api/client';
import './TaskboardPanel.css';

export interface TaskboardPanelProps {
  onNavigate: (panel: 'review' | 'kg' | 'prune') => void;
  onClose:    () => void;
}

export function TaskboardPanel({ onNavigate, onClose }: TaskboardPanelProps) {
  const [reviewCount, setReviewCount] = useState(0);
  const [pruneCount,  setPruneCount]  = useState(0);
  const [loading,     setLoading]     = useState(true);

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'taskboard' });
    void load();
    return () => dispatch('cyber:panel:closed', { panelId: 'taskboard' });
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [items, prune] = await Promise.all([getReviewItems(), getPruneCandidates()]);
      setReviewCount(items.length);
      setPruneCount(prune.stats.critical + prune.stats.warning);
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  };

  const total = reviewCount + pruneCount;

  return (
    <div className="taskboard-overlay">
      <div className="taskboard-box">
        <div className="taskboard-title-bar">
          <span className="taskboard-title">📋 任务板</span>
          <button className="btn-pixel" onClick={onClose} data-testid="taskboard-close">×</button>
        </div>

        {loading ? (
          <div className="taskboard-loading">加载中…</div>
        ) : total === 0 ? (
          <div className="taskboard-empty" data-testid="taskboard-empty">
            所有任务已处理完毕 ✓
          </div>
        ) : (
          <div className="taskboard-items">
            {reviewCount > 0 && (
              <button
                className="taskboard-row taskboard-row--review"
                onClick={() => onNavigate('review')}
                data-testid="taskboard-review-row"
              >
                <span className="taskboard-badge taskboard-badge--red">{reviewCount}</span>
                <div className="taskboard-row-text">
                  <div className="taskboard-row-title">蓄水池待审批</div>
                  <div className="taskboard-row-desc">待人工决策的 AI 观察</div>
                </div>
              </button>
            )}
            {pruneCount > 0 && (
              <button
                className="taskboard-row taskboard-row--prune"
                onClick={() => onNavigate('prune')}
                data-testid="taskboard-prune-row"
              >
                <span className="taskboard-badge taskboard-badge--gray">{pruneCount}</span>
                <div className="taskboard-row-text">
                  <div className="taskboard-row-title">节点老化提醒</div>
                  <div className="taskboard-row-desc">进入老化阈值的节点</div>
                </div>
              </button>
            )}
            <button
              className="taskboard-row taskboard-row--kg"
              onClick={() => onNavigate('kg')}
              data-testid="taskboard-kg-row"
            >
              <span className="taskboard-badge taskboard-badge--neutral">📖</span>
              <div className="taskboard-row-text">
                <div className="taskboard-row-title">浏览认知图谱</div>
                <div className="taskboard-row-desc">查看 Id / Ego / Superego 节点</div>
              </div>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create TaskboardPanel.css**

Create `frontend/src/components/panels/TaskboardPanel.css`:

```css
.taskboard-overlay {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(26, 8, 0, 0.80);
}

.taskboard-box {
  background: var(--panel-bg);
  border: var(--border-width) solid var(--panel-border);
  box-shadow: var(--pixel-shadow);
  width: 360px;
  font-family: var(--font-mono);
}

.taskboard-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--panel-title-bg);
  border-bottom: var(--border-width) solid var(--panel-border);
}
.taskboard-title {
  font-family: var(--font-pixel);
  font-size: 8px;
  color: var(--panel-gold);
}

.taskboard-loading,
.taskboard-empty {
  padding: 24px;
  text-align: center;
  font-size: 10px;
  color: var(--panel-text-dim);
}

.taskboard-items {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.taskboard-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--panel-bg);
  border: none;
  border-bottom: 1px solid var(--panel-border);
  cursor: pointer;
  text-align: left;
  width: 100%;
  font-family: var(--font-mono);
  transition: background 0.1s;
}
.taskboard-row:hover { background: var(--panel-bg-card); }
.taskboard-row:last-child { border-bottom: none; }

.taskboard-badge {
  font-size: 12px;
  font-weight: bold;
  min-width: 28px;
  text-align: center;
  padding: 2px 6px;
  border: 2px solid currentColor;
}
.taskboard-badge--red     { color: var(--color-id); }
.taskboard-badge--gray    { color: #8b8b8b; }
.taskboard-badge--neutral { color: var(--panel-text-dim); border: none; font-size: 16px; }

.taskboard-row-title {
  font-size: 10px;
  color: var(--panel-text);
  margin-bottom: 2px;
}
.taskboard-row-desc {
  font-size: 8px;
  color: var(--panel-text-dim);
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/panels/TaskboardPanel.test.tsx
```
Expected: PASS — 5 tests

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/components/panels/TaskboardPanel.tsx src/components/panels/TaskboardPanel.css src/components/panels/TaskboardPanel.test.tsx
git commit -m "feat: add TaskboardPanel with review and prune item counts"
```

---

### Task 4: ReviewPanel

**Files:**
- Create: `frontend/src/components/panels/ReviewPanel.tsx`
- Create: `frontend/src/components/panels/ReviewPanel.css`
- Create: `frontend/src/components/panels/ReviewPanel.test.tsx`

Context: Step-through approval panel. Loads all pending review items on mount. Shows one item at a time with progress counter. Description block is visible by default (spec says default = shown) and when Y is selected; hidden when N or S is selected. Q immediately skips to next without API call. Y/N/S require clicking "提交" to confirm. On successful submit, dispatches `cyber:review:done`. When all items are processed, calls `onBack`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/panels/ReviewPanel.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ReviewPanel } from './ReviewPanel';
import { getReviewItems, decideReviewItem } from '../../api/client';

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client', () => ({
  getReviewItems: vi.fn(),
  decideReviewItem: vi.fn(),
}));

const ITEM = {
  id: 'item-1', pendingId: 'p1', timestamp: '2026-01-01', sourceMode: '健身房',
  content: '用户早起频率提升', rawEvidence: 'evidence text',
  proposedRoute: 'approved_kg', proposedLayer: 'Ego',
  aiRationale: 'AI rationale text', importance: 7, importanceNote: 'note',
};

describe('ReviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getReviewItems).mockResolvedValue([ITEM]);
    vi.mocked(decideReviewItem).mockResolvedValue(undefined);
  });

  it('renders item content after loading', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('review-content')).toBeInTheDocument());
    expect(screen.getByTestId('review-content')).toHaveTextContent('用户早起频率提升');
  });

  it('shows description block by default', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('review-description-block')).toBeInTheDocument());
  });

  it('hides description block when N is selected', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-n'));
    fireEvent.click(screen.getByTestId('review-btn-n'));
    expect(screen.queryByTestId('review-description-block')).toBeNull();
  });

  it('shows description block again when Y is selected after N', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-n'));
    fireEvent.click(screen.getByTestId('review-btn-n'));
    fireEvent.click(screen.getByTestId('review-btn-y'));
    expect(screen.getByTestId('review-description-block')).toBeInTheDocument();
  });

  it('calls decideReviewItem and dispatches review:done on Y submit', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-y'));
    fireEvent.click(screen.getByTestId('review-btn-y'));
    await act(async () => { fireEvent.click(screen.getByTestId('review-submit')); });
    expect(decideReviewItem).toHaveBeenCalledWith('item-1', expect.objectContaining({ decision: 'approved_kg' }));
    expect(mockDispatch).toHaveBeenCalledWith('cyber:review:done', { processedCount: 1 });
  });

  it('Q skips to empty state without calling API', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-q'));
    fireEvent.click(screen.getByTestId('review-btn-q'));
    expect(decideReviewItem).not.toHaveBeenCalled();
    expect(screen.getByTestId('review-empty')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/panels/ReviewPanel.test.tsx
```
Expected: error — `Cannot find module './ReviewPanel'`

- [ ] **Step 3: Create ReviewPanel.tsx**

Create `frontend/src/components/panels/ReviewPanel.tsx`:

```tsx
import { useState, useEffect } from 'react';
import { dispatch } from '../../eventbus';
import { getReviewItems, decideReviewItem, type ReviewItem } from '../../api/client';
import './ReviewPanel.css';

export function ReviewPanel({ onBack }: { onBack: () => void }) {
  const [items,      setItems]      = useState<ReviewItem[]>([]);
  const [index,      setIndex]      = useState(0);
  const [decision,   setDecision]   = useState<'approved_kg' | 'rejected' | 'approved_log' | null>(null);
  const [userNote,   setUserNote]   = useState('');
  const [description, setDescription] = useState('');
  const [importance, setImportance] = useState(7);
  const [loading,    setLoading]    = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [done,       setDone]       = useState(false);

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'review' });
    void load();
    return () => dispatch('cyber:panel:closed', { panelId: 'review' });
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getReviewItems();
      setItems(data);
      if (data.length > 0) {
        setDescription(data[0].content);
        setImportance(data[0].importance ?? 7);
      } else {
        setDone(true);
      }
    } finally { setLoading(false); }
  };

  const currentItem = items[index];
  const showDescription = decision === null || decision === 'approved_kg';

  const selectDecision = (d: 'approved_kg' | 'rejected' | 'approved_log') => {
    setDecision(d);
  };

  const handleSubmit = async () => {
    if (!currentItem || !decision) return;
    setSubmitting(true);
    try {
      await decideReviewItem(currentItem.id, {
        decision,
        userNote:    userNote || undefined,
        importance:  decision === 'approved_kg' ? importance  : undefined,
        description: decision === 'approved_kg' ? description : undefined,
      });
      dispatch('cyber:review:done', { processedCount: 1 });
      advance();
    } finally { setSubmitting(false); }
  };

  const handleSkip = () => { advance(); };

  const advance = () => {
    const next = index + 1;
    if (next >= items.length) {
      setDone(true);
    } else {
      setIndex(next);
      setDecision(null);
      setUserNote('');
      setDescription(items[next].content);
      setImportance(items[next].importance ?? 7);
    }
  };

  if (loading) {
    return (
      <div className="review-panel">
        <div className="review-loading">加载中…</div>
      </div>
    );
  }

  if (done || !currentItem) {
    return (
      <div className="review-panel">
        <div className="review-empty" data-testid="review-empty">
          <div>所有审批项已处理完毕 ✓</div>
          <button className="btn-pixel" onClick={onBack} data-testid="review-back">← 返回</button>
        </div>
      </div>
    );
  }

  return (
    <div className="review-panel">
      <div className="review-header">
        <button className="btn-pixel review-back-btn" onClick={onBack} data-testid="review-back">
          ← 返回
        </button>
        <span className="review-progress">{index + 1} / {items.length}</span>
        <span className="review-source-tag">{currentItem.sourceMode}</span>
      </div>

      <div className="review-body">
        <div className="review-card" data-testid="review-content">
          {currentItem.content}
        </div>

        <div className="review-ai-hint">
          <span>AI 建议：{currentItem.proposedRoute === 'approved_kg' ? '写入图谱' : '只记日志'}</span>
          {currentItem.proposedLayer && (
            <span className={`review-layer-tag review-layer-tag--${currentItem.proposedLayer.toLowerCase()}`}>
              {currentItem.proposedLayer}
            </span>
          )}
          {currentItem.importance != null && (
            <span className="review-ai-importance">重要度 {currentItem.importance}</span>
          )}
        </div>

        <textarea
          className="review-user-note"
          value={userNote}
          onChange={e => setUserNote(e.target.value)}
          placeholder="你的看法或纠正（可选）"
          rows={2}
          data-testid="review-user-note"
        />

        {showDescription && (
          <div className="review-description-block" data-testid="review-description-block">
            <div className="review-label">写入图谱的描述</div>
            <textarea
              className="review-description-input"
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={3}
              data-testid="review-description"
            />
            <div className="review-importance-row">
              <span className="review-label">重要度</span>
              <input
                type="range" min={1} max={10}
                value={importance}
                onChange={e => setImportance(Number(e.target.value))}
                className="review-importance-slider"
                data-testid="review-importance-slider"
              />
              <span className="review-importance-value" data-testid="review-importance-value">
                {importance}
              </span>
            </div>
          </div>
        )}

        <div className="review-actions">
          <button
            className={`btn-pixel review-btn review-btn--y${decision === 'approved_kg' ? ' review-btn--selected' : ''}`}
            onClick={() => selectDecision('approved_kg')}
            data-testid="review-btn-y"
          >Y 写入图谱</button>
          <button
            className={`btn-pixel review-btn review-btn--n${decision === 'rejected' ? ' review-btn--selected' : ''}`}
            onClick={() => selectDecision('rejected')}
            data-testid="review-btn-n"
          >N 拒绝</button>
          <button
            className={`btn-pixel review-btn review-btn--s${decision === 'approved_log' ? ' review-btn--selected' : ''}`}
            onClick={() => selectDecision('approved_log')}
            data-testid="review-btn-s"
          >S 记日志</button>
          <button
            className="btn-pixel review-btn review-btn--q"
            onClick={handleSkip}
            data-testid="review-btn-q"
          >Q 跳过</button>
        </div>

        {decision !== null && (
          <button
            className="btn-pixel review-submit"
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="review-submit"
          >
            {submitting ? '提交中…' : '提交'}
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create ReviewPanel.css**

Create `frontend/src/components/panels/ReviewPanel.css`:

```css
.review-panel {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: flex;
  flex-direction: column;
  background: var(--panel-bg);
  font-family: var(--font-mono);
  overflow-y: auto;
}

.review-loading,
.review-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  font-size: 10px;
  color: var(--panel-text-dim);
}

.review-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--panel-title-bg);
  border-bottom: var(--border-width) solid var(--panel-border);
  flex-shrink: 0;
}

.review-progress {
  font-family: var(--font-pixel);
  font-size: 8px;
  color: var(--panel-gold);
}

.review-source-tag {
  font-size: 8px;
  color: var(--panel-gold);
  background: var(--panel-mid-bg);
  border: 1px solid var(--panel-border);
  padding: 2px 6px;
}

.review-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  max-width: 680px;
  width: 100%;
  margin: 0 auto;
}

.review-card {
  background: var(--panel-bg-card);
  border: var(--border-width) solid var(--panel-border);
  padding: 12px;
  font-size: 11px;
  color: var(--panel-text);
  line-height: 1.7;
}

.review-ai-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 9px;
  color: var(--panel-text-dim);
}

.review-layer-tag {
  font-size: 8px;
  padding: 1px 6px;
  border: 1px solid;
}
.review-layer-tag--id        { color: var(--color-id);        border-color: var(--color-id); }
.review-layer-tag--ego       { color: var(--color-ego);       border-color: var(--color-ego); }
.review-layer-tag--superego  { color: var(--color-superego);  border-color: var(--color-superego); }

.review-ai-importance { font-size: 9px; color: var(--panel-text-dim); }

.review-user-note,
.review-description-input {
  width: 100%;
  font-family: var(--font-mono);
  font-size: 10px;
  background: var(--panel-bg-card);
  color: var(--panel-text);
  border: var(--border-width) solid var(--panel-border);
  padding: 8px;
  resize: vertical;
}

.review-description-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-label {
  font-size: 8px;
  color: var(--panel-text-dim);
  font-weight: bold;
}

.review-importance-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.review-importance-slider { flex: 1; accent-color: var(--panel-title-bg); }
.review-importance-value {
  font-size: 12px;
  font-weight: bold;
  color: var(--panel-text);
  min-width: 24px;
  text-align: center;
}

.review-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.review-btn { flex: 1; text-align: center; font-size: 9px; padding: 8px 4px; }
.review-btn--y         { color: var(--color-ego);  border-color: var(--color-ego); }
.review-btn--n         { color: var(--color-id);   border-color: var(--color-id); }
.review-btn--s         { color: var(--panel-gold); border-color: var(--panel-gold); }
.review-btn--q         { color: var(--panel-text-dim); }
.review-btn--selected  { filter: brightness(1.3); box-shadow: 0 0 0 2px var(--panel-gold); }

.review-submit {
  width: 100%;
  font-size: 10px;
  padding: 10px;
  background: var(--panel-title-bg);
  color: var(--panel-gold);
  border-color: var(--panel-gold);
}
.review-submit:disabled { opacity: 0.5; cursor: not-allowed; }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/panels/ReviewPanel.test.tsx
```
Expected: PASS — 6 tests

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/components/panels/ReviewPanel.tsx src/components/panels/ReviewPanel.css src/components/panels/ReviewPanel.test.tsx
git commit -m "feat: add ReviewPanel with Y/N/S/Q approval flow"
```

---

### Task 5: KGPanel

**Files:**
- Create: `frontend/src/components/panels/KGPanel.tsx`
- Create: `frontend/src/components/panels/KGPanel.css`
- Create: `frontend/src/components/panels/KGPanel.test.tsx`

Context: Knowledge graph browser with tabs (全部/Id/Ego/Superego/归档). Fetches all nodes including archived on mount (single call, `includeArchived=true`), filters client-side. Archived nodes get `opacity: 0.6` via CSS class. Clicking a node card expands it to show full content. A `?` button in the tab bar explains the three-layer concept.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/panels/KGPanel.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KGPanel } from './KGPanel';
import { getKgNodes } from '../../api/client';

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client', () => ({ getKgNodes: vi.fn() }));

const NODES = [
  { id: 'n1', label: '早起习惯', layer: 'Ego' as const, description: 'Ego desc', importance: 8,
    evidence: [], createdAt: null, lastAccessed: null, archived: false, archiveReason: null },
  { id: 'n2', label: '旧记忆', layer: 'Id' as const, description: 'Id desc', importance: 2,
    evidence: [], createdAt: null, lastAccessed: null, archived: true, archiveReason: '过期' },
];

describe('KGPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getKgNodes).mockResolvedValue(NODES);
  });

  it('renders all tab buttons', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    expect(screen.getByTestId('tab-all')).toBeInTheDocument();
    expect(screen.getByTestId('tab-Id')).toBeInTheDocument();
    expect(screen.getByTestId('tab-Ego')).toBeInTheDocument();
    expect(screen.getByTestId('tab-Superego')).toBeInTheDocument();
    expect(screen.getByTestId('tab-archived')).toBeInTheDocument();
  });

  it('shows active nodes on 全部 tab (excludes archived)', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    expect(screen.getByText('早起习惯')).toBeInTheDocument();
    expect(screen.queryByText('旧记忆')).toBeNull();
  });

  it('shows archived nodes on 归档 tab', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    fireEvent.click(screen.getByTestId('tab-archived'));
    expect(screen.getByText('旧记忆')).toBeInTheDocument();
    expect(screen.queryByText('早起习惯')).toBeNull();
  });

  it('clicking node card expands detail', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    fireEvent.click(screen.getByTestId('kg-node-n1'));
    expect(screen.getByTestId('kg-expanded')).toBeInTheDocument();
  });

  it('calls onBack when back button clicked', async () => {
    const onBack = vi.fn();
    render(<KGPanel onBack={onBack} />);
    await waitFor(() => screen.getByTestId('kg-back'));
    fireEvent.click(screen.getByTestId('kg-back'));
    expect(onBack).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/panels/KGPanel.test.tsx
```
Expected: error — `Cannot find module './KGPanel'`

- [ ] **Step 3: Create KGPanel.tsx**

Create `frontend/src/components/panels/KGPanel.tsx`:

```tsx
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
        <div className="kg-help-card">{LAYER_HELP.split('\n').map(l => <div key={l}>{l}</div>)}</div>
      )}

      <div className="kg-tabs">
        {(['all', 'Id', 'Ego', 'Superego', 'archived'] as Tab[]).map(tab => (
          <button
            key={tab}
            className={`btn-pixel kg-tab${activeTab === tab ? ' kg-tab--active' : ''}`}
            onClick={() => { setActiveTab(tab); setExpandedId(null); }}
            data-testid={`tab-${tab}`}
            style={activeTab === tab && LAYER_COLOR[tab] ? { borderColor: LAYER_COLOR[tab], color: LAYER_COLOR[tab] } : undefined}
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
```

- [ ] **Step 4: Create KGPanel.css**

Create `frontend/src/components/panels/KGPanel.css`:

```css
.kg-panel {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: flex;
  flex-direction: column;
  background: var(--panel-bg);
  font-family: var(--font-mono);
  overflow: hidden;
}

.kg-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--panel-title-bg);
  border-bottom: var(--border-width) solid var(--panel-border);
  flex-shrink: 0;
}

.kg-panel-title {
  flex: 1;
  font-family: var(--font-pixel);
  font-size: 8px;
  color: var(--panel-gold);
}

.kg-help-card {
  background: var(--panel-shadow);
  color: var(--panel-gold);
  font-size: 9px;
  padding: 8px 16px;
  border-bottom: var(--border-width) solid var(--panel-border);
  line-height: 1.8;
}

.kg-tabs {
  display: flex;
  gap: 0;
  border-bottom: var(--border-width) solid var(--panel-border);
  background: var(--panel-mid-bg);
  flex-shrink: 0;
  overflow-x: auto;
}
.kg-tab {
  flex: 1;
  font-size: 8px;
  border: none;
  border-right: 1px solid var(--panel-border);
  background: transparent;
  padding: 6px 4px;
  box-shadow: none;
}
.kg-tab:last-child { border-right: none; }
.kg-tab--active {
  background: var(--panel-bg-card);
  font-weight: bold;
}

.kg-loading, .kg-empty {
  padding: 24px;
  text-align: center;
  font-size: 10px;
  color: var(--panel-text-dim);
}

.kg-node-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kg-node-card {
  display: flex;
  align-items: stretch;
  background: var(--panel-bg-card);
  border: 1px solid var(--panel-border);
  cursor: pointer;
  text-align: left;
  width: 100%;
  font-family: var(--font-mono);
  padding: 0;
}
.kg-node-card:hover { filter: brightness(1.05); }
.kg-node-card--archived { opacity: 0.6; }

.kg-node-color-bar {
  width: 4px;
  flex-shrink: 0;
  align-self: stretch;
}

.kg-node-body {
  flex: 1;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.kg-node-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kg-node-label { font-size: 11px; font-weight: bold; color: var(--panel-text); }
.kg-node-importance { font-size: 9px; color: var(--panel-text-dim); }
.kg-node-layer-tag { font-size: 8px; color: var(--panel-text-dim); }
.kg-node-desc {
  font-size: 9px;
  color: var(--panel-text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kg-expanded-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(26, 8, 0, 0.75);
}

.kg-expanded-card {
  background: var(--panel-bg);
  border: var(--border-width) solid var(--panel-border);
  box-shadow: var(--pixel-shadow);
  width: 480px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.kg-expanded-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--panel-title-bg);
  border-bottom: var(--border-width) solid var(--panel-border);
}
.kg-expanded-layer { font-size: 9px; font-weight: bold; }
.kg-expanded-title { flex: 1; font-size: 12px; font-weight: bold; color: var(--panel-gold); }

.kg-expanded-desc {
  flex: 1;
  padding: 12px;
  font-size: 11px;
  color: var(--panel-text);
  line-height: 1.7;
  overflow-y: auto;
}

.kg-expanded-meta {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  font-size: 9px;
  color: var(--panel-text-dim);
  border-top: 1px solid var(--panel-border);
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/panels/KGPanel.test.tsx
```
Expected: PASS — 5 tests

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/components/panels/KGPanel.tsx src/components/panels/KGPanel.css src/components/panels/KGPanel.test.tsx
git commit -m "feat: add KGPanel node browser with layer tabs"
```

---

### Task 6: PrunePanel

**Files:**
- Create: `frontend/src/components/panels/PrunePanel.tsx`
- Create: `frontend/src/components/panels/PrunePanel.css`
- Create: `frontend/src/components/panels/PrunePanel.test.tsx`

Context: Aging management panel. Loads candidates on mount with stats (critical/warning/healthy counts). For each candidate node: archive calls `archiveNode(id, '')`, skip removes it from local list without API call, boost shows a number input then calls `boostNode(id, value)`. Stats show in three colored grid cells.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/panels/PrunePanel.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PrunePanel } from './PrunePanel';
import { getPruneCandidates, archiveNode, boostNode } from '../../api/client';

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client', () => ({
  getPruneCandidates: vi.fn(),
  archiveNode: vi.fn(),
  boostNode: vi.fn(),
}));

const NODE = {
  id: 'n1', label: '早起习惯', layer: 'Ego' as const, description: 'desc',
  importance: 3, evidence: [], createdAt: null, lastAccessed: '2026-01-01',
  archived: false, archiveReason: null,
};
const PRUNE_DATA = {
  stats: { critical: 1, warning: 2, healthy: 10 },
  candidates: [{ node: NODE, stalenessScore: 9.2, severity: 'critical' as const }],
};

describe('PrunePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPruneCandidates).mockResolvedValue(PRUNE_DATA);
    vi.mocked(archiveNode).mockResolvedValue(undefined);
    vi.mocked(boostNode).mockResolvedValue(undefined);
  });

  it('renders stats grid with correct counts', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('prune-critical')).toBeInTheDocument());
    expect(screen.getByTestId('prune-critical')).toHaveTextContent('1');
    expect(screen.getByTestId('prune-warning')).toHaveTextContent('2');
    expect(screen.getByTestId('prune-healthy')).toHaveTextContent('10');
  });

  it('shows candidate node label', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('早起习惯')).toBeInTheDocument());
  });

  it('archive button calls archiveNode and removes node from list', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('prune-archive-n1'));
    await act(async () => { fireEvent.click(screen.getByTestId('prune-archive-n1')); });
    expect(archiveNode).toHaveBeenCalledWith('n1', '');
    expect(screen.queryByText('早起习惯')).toBeNull();
  });

  it('skip removes node from list without calling API', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('prune-skip-n1'));
    fireEvent.click(screen.getByTestId('prune-skip-n1'));
    expect(archiveNode).not.toHaveBeenCalled();
    expect(screen.queryByText('早起习惯')).toBeNull();
  });

  it('boost shows input, then calls boostNode with entered value', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('prune-boost-n1'));
    fireEvent.click(screen.getByTestId('prune-boost-n1'));
    expect(screen.getByTestId('prune-boost-input-n1')).toBeInTheDocument();
    fireEvent.change(screen.getByTestId('prune-boost-input-n1'), { target: { value: '8' } });
    await act(async () => { fireEvent.click(screen.getByTestId('prune-boost-confirm-n1')); });
    expect(boostNode).toHaveBeenCalledWith('n1', 8);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/panels/PrunePanel.test.tsx
```
Expected: error — `Cannot find module './PrunePanel'`

- [ ] **Step 3: Create PrunePanel.tsx**

Create `frontend/src/components/panels/PrunePanel.tsx`:

```tsx
import { useState, useEffect } from 'react';
import { dispatch } from '../../eventbus';
import { getPruneCandidates, archiveNode, boostNode, type PruneStats, type PruneCandidate } from '../../api/client';
import './PrunePanel.css';

export function PrunePanel({ onBack }: { onBack: () => void }) {
  const [stats,      setStats]      = useState<PruneStats>({ critical: 0, warning: 0, healthy: 0 });
  const [candidates, setCandidates] = useState<PruneCandidate[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [boostingId, setBoostingId] = useState<string | null>(null);
  const [boostValue, setBoostValue] = useState('7');

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'prune' });
    void getPruneCandidates()
      .then(data => { setStats(data.stats); setCandidates(data.candidates); })
      .finally(() => setLoading(false));
    return () => dispatch('cyber:panel:closed', { panelId: 'prune' });
  }, []);

  const handleArchive = async (id: string) => {
    await archiveNode(id, '');
    setCandidates(prev => prev.filter(c => c.node.id !== id));
  };

  const handleSkip = (id: string) => {
    setCandidates(prev => prev.filter(c => c.node.id !== id));
  };

  const handleBoostConfirm = async (id: string) => {
    const val = parseInt(boostValue, 10);
    if (isNaN(val) || val < 1 || val > 10) return;
    await boostNode(id, val);
    setCandidates(prev => prev.filter(c => c.node.id !== id));
    setBoostingId(null);
  };

  return (
    <div className="prune-panel">
      <div className="prune-header">
        <button className="btn-pixel" onClick={onBack} data-testid="prune-back">← 返回</button>
        <span className="prune-title">老化管理</span>
      </div>

      {!loading && (
        <div className="prune-stats-grid">
          <div className="prune-stat prune-stat--critical">
            <div className="prune-stat-count" data-testid="prune-critical">{stats.critical}</div>
            <div className="prune-stat-label">紧急</div>
          </div>
          <div className="prune-stat prune-stat--warning">
            <div className="prune-stat-count" data-testid="prune-warning">{stats.warning}</div>
            <div className="prune-stat-label">接近</div>
          </div>
          <div className="prune-stat prune-stat--healthy">
            <div className="prune-stat-count" data-testid="prune-healthy">{stats.healthy}</div>
            <div className="prune-stat-label">健康</div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="prune-loading">加载中…</div>
      ) : candidates.length === 0 ? (
        <div className="prune-empty">暂无需处理的老化节点 ✓</div>
      ) : (
        <div className="prune-candidate-list">
          {candidates.map(c => (
            <div
              key={c.node.id}
              className={`prune-candidate prune-candidate--${c.severity}`}
            >
              <div className="prune-candidate-info">
                <div className="prune-candidate-label">{c.node.label}</div>
                <div className="prune-candidate-meta">
                  <span>老化分 {c.stalenessScore.toFixed(1)}</span>
                  <span>·</span>
                  <span>重要度 {c.node.importance}</span>
                  <span>·</span>
                  <span className={`prune-severity prune-severity--${c.severity}`}>
                    {c.severity === 'critical' ? '紧急' : c.severity === 'warning' ? '接近' : '健康'}
                  </span>
                </div>
              </div>

              {boostingId === c.node.id ? (
                <div className="prune-boost-row">
                  <input
                    type="number" min={1} max={10}
                    value={boostValue}
                    onChange={e => setBoostValue(e.target.value)}
                    className="prune-boost-input"
                    data-testid={`prune-boost-input-${c.node.id}`}
                  />
                  <button
                    className="btn-pixel prune-boost-confirm"
                    onClick={() => void handleBoostConfirm(c.node.id)}
                    data-testid={`prune-boost-confirm-${c.node.id}`}
                  >确认</button>
                  <button
                    className="btn-pixel"
                    onClick={() => setBoostingId(null)}
                  >取消</button>
                </div>
              ) : (
                <div className="prune-candidate-actions">
                  <button
                    className="btn-pixel prune-btn-archive"
                    onClick={() => void handleArchive(c.node.id)}
                    data-testid={`prune-archive-${c.node.id}`}
                  >归档</button>
                  <button
                    className="btn-pixel prune-btn-boost"
                    onClick={() => { setBoostingId(c.node.id); setBoostValue(String(c.node.importance)); }}
                    data-testid={`prune-boost-${c.node.id}`}
                  >提升重要度</button>
                  <button
                    className="btn-pixel prune-btn-skip"
                    onClick={() => handleSkip(c.node.id)}
                    data-testid={`prune-skip-${c.node.id}`}
                  >跳过</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create PrunePanel.css**

Create `frontend/src/components/panels/PrunePanel.css`:

```css
.prune-panel {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: flex;
  flex-direction: column;
  background: var(--panel-bg);
  font-family: var(--font-mono);
  overflow: hidden;
}

.prune-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--panel-title-bg);
  border-bottom: var(--border-width) solid var(--panel-border);
  flex-shrink: 0;
}

.prune-title {
  font-family: var(--font-pixel);
  font-size: 8px;
  color: var(--panel-gold);
}

.prune-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  border-bottom: var(--border-width) solid var(--panel-border);
  flex-shrink: 0;
}

.prune-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
  border-right: 1px solid var(--panel-border);
}
.prune-stat:last-child { border-right: none; }

.prune-stat-count {
  font-size: 20px;
  font-weight: bold;
  font-family: var(--font-pixel);
}
.prune-stat-label { font-size: 8px; color: var(--panel-text-dim); margin-top: 4px; }

.prune-stat--critical .prune-stat-count { color: var(--color-id); }
.prune-stat--warning  .prune-stat-count { color: var(--color-superego); }
.prune-stat--healthy  .prune-stat-count { color: var(--color-ego); }

.prune-loading, .prune-empty {
  padding: 24px;
  text-align: center;
  font-size: 10px;
  color: var(--panel-text-dim);
}

.prune-candidate-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.prune-candidate {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--panel-border);
  border-left: 4px solid transparent;
}
.prune-candidate--critical { border-left-color: var(--color-id); }
.prune-candidate--warning  { border-left-color: var(--color-superego); }
.prune-candidate--healthy  { border-left-color: var(--color-ego); }

.prune-candidate-info { flex: 1; }
.prune-candidate-label { font-size: 11px; font-weight: bold; color: var(--panel-text); }
.prune-candidate-meta {
  display: flex;
  gap: 8px;
  font-size: 8px;
  color: var(--panel-text-dim);
  margin-top: 4px;
}

.prune-severity { font-weight: bold; }
.prune-severity--critical { color: var(--color-id); }
.prune-severity--warning  { color: var(--color-superego); }
.prune-severity--healthy  { color: var(--color-ego); }

.prune-candidate-actions { display: flex; gap: 6px; flex-shrink: 0; }

.prune-btn-archive { color: var(--color-id);  border-color: var(--color-id); }
.prune-btn-boost   { color: var(--color-superego); border-color: var(--color-superego); }

.prune-boost-row { display: flex; gap: 6px; align-items: center; }
.prune-boost-input {
  width: 50px;
  font-family: var(--font-mono);
  font-size: 10px;
  background: var(--panel-bg-card);
  color: var(--panel-text);
  border: var(--border-width) solid var(--panel-border);
  padding: 4px;
  text-align: center;
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/panels/PrunePanel.test.tsx
```
Expected: PASS — 5 tests

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/components/panels/PrunePanel.tsx src/components/panels/PrunePanel.css src/components/panels/PrunePanel.test.tsx
git commit -m "feat: add PrunePanel with archive/boost/skip per candidate"
```

---

### Task 7: App.tsx Wiring + Tests

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`
- Create: `frontend/src/App.test.tsx`

Context: App.tsx becomes the panel state coordinator. Add `useAuth` to check `isOwner`. Add `ActivePanel` discriminated union as local state. Add `useEffect` listening to `cyber:npc:interact` and `cyber:object:interact` (taskboard + kg object ids). Render WelcomePage early-return for unenterd visitors. Mount each panel conditionally. Update App.css to add pointer-events for new panels.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/App.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';
import { AuthContext, type AuthContextValue } from './contexts/AuthContext';

vi.mock('./game/PhaserGame',           () => ({ PhaserGame: () => <div data-testid="phaser-game" /> }));
vi.mock('./components/HUD',            () => ({ HUD: () => <div data-testid="hud" /> }));
vi.mock('./components/panels/RoomEntryPrompt', () => ({ RoomEntryPrompt: () => <div /> }));
vi.mock('./components/panels/DialoguePanel',   () => ({
  DialoguePanel: ({ npcName }: { npcName: string }) => <div data-testid="dialogue-panel">{npcName}</div>,
}));
vi.mock('./components/panels/TaskboardPanel',  () => ({
  TaskboardPanel: () => <div data-testid="taskboard-panel" />,
}));
vi.mock('./components/panels/ReviewPanel',     () => ({
  ReviewPanel: () => <div data-testid="review-panel" />,
}));
vi.mock('./components/panels/KGPanel',         () => ({
  KGPanel: () => <div data-testid="kg-panel" />,
}));
vi.mock('./components/panels/PrunePanel',      () => ({
  PrunePanel: () => <div data-testid="prune-panel" />,
}));
vi.mock('./pages/WelcomePage', () => ({
  WelcomePage: ({ onEnter }: { onEnter: () => void }) => (
    <button data-testid="welcome-enter" onClick={onEnter}>进入空间</button>
  ),
}));

const asOwner   = { isOwner: true,  privateKey: 'k' } satisfies AuthContextValue;
const asVisitor = { isOwner: false, privateKey: '' }  satisfies AuthContextValue;

describe('App', () => {
  it('shows WelcomePage for visitor before entering', () => {
    render(<AuthContext.Provider value={asVisitor}><App /></AuthContext.Provider>);
    expect(screen.getByTestId('welcome-enter')).toBeInTheDocument();
    expect(screen.queryByTestId('phaser-game')).toBeNull();
  });

  it('shows game world for owner without welcome page', () => {
    render(<AuthContext.Provider value={asOwner}><App /></AuthContext.Provider>);
    expect(screen.getByTestId('phaser-game')).toBeInTheDocument();
    expect(screen.queryByTestId('welcome-enter')).toBeNull();
  });

  it('enters game world after visitor clicks welcome button', async () => {
    render(<AuthContext.Provider value={asVisitor}><App /></AuthContext.Provider>);
    fireEvent.click(screen.getByTestId('welcome-enter'));
    await waitFor(() => expect(screen.getByTestId('phaser-game')).toBeInTheDocument());
    expect(screen.queryByTestId('welcome-enter')).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/App.test.tsx
```
Expected: FAIL — `App` doesn't yet render `WelcomePage` or gate on `entered` state

- [ ] **Step 3: Modify App.tsx**

Replace `frontend/src/App.tsx` entirely with:

```tsx
import { useState, useEffect } from 'react';
import { PhaserGame }       from './game/PhaserGame';
import { HUD }              from './components/HUD';
import { RoomEntryPrompt }  from './components/panels/RoomEntryPrompt';
import { DialoguePanel }    from './components/panels/DialoguePanel';
import { TaskboardPanel }   from './components/panels/TaskboardPanel';
import { ReviewPanel }      from './components/panels/ReviewPanel';
import { KGPanel }          from './components/panels/KGPanel';
import { PrunePanel }       from './components/panels/PrunePanel';
import { WelcomePage }      from './pages/WelcomePage';
import { useAuth }          from './contexts/AuthContext';
import { listen }           from './eventbus';
import './styles/tokens.css';
import './App.css';

type ActivePanel =
  | { id: 'dialogue'; npcId: string; npcName: string }
  | { id: 'taskboard' }
  | { id: 'review' }
  | { id: 'kg' }
  | { id: 'prune' }
  | null;

export default function App() {
  const { isOwner } = useAuth();
  const [entered,     setEntered]     = useState(isOwner);
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);

  useEffect(() => {
    const offNpc = listen('cyber:npc:interact', ({ npcId, npcName }) => {
      setActivePanel({ id: 'dialogue', npcId, npcName });
    });
    const offObj = listen('cyber:object:interact', ({ objectId }) => {
      if (objectId === 'taskboard' && isOwner) setActivePanel({ id: 'taskboard' });
      if (objectId === 'kg'        && isOwner) setActivePanel({ id: 'kg' });
    });
    return () => { offNpc(); offObj(); };
  }, [isOwner]);

  if (!entered) {
    return <WelcomePage onEnter={() => setEntered(true)} />;
  }

  return (
    <>
      <PhaserGame />
      <div id="panel-layer">
        <HUD />
        <RoomEntryPrompt />

        {activePanel?.id === 'dialogue' && (
          <DialoguePanel
            npcId={activePanel.npcId}
            npcName={activePanel.npcName}
            onClose={() => setActivePanel(null)}
          />
        )}

        {isOwner && activePanel?.id === 'taskboard' && (
          <TaskboardPanel
            onNavigate={(p) => setActivePanel({ id: p })}
            onClose={() => setActivePanel(null)}
          />
        )}

        {isOwner && activePanel?.id === 'review' && (
          <ReviewPanel onBack={() => setActivePanel({ id: 'taskboard' })} />
        )}

        {isOwner && activePanel?.id === 'kg' && (
          <KGPanel onBack={() => setActivePanel({ id: 'taskboard' })} />
        )}

        {isOwner && activePanel?.id === 'prune' && (
          <PrunePanel onBack={() => setActivePanel({ id: 'taskboard' })} />
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 4: Modify App.css**

Replace `frontend/src/App.css` entirely with:

```css
#panel-layer {
  position: relative;
  z-index: 10;
  pointer-events: none; /* clicks fall through to Phaser by default */
}

/* Re-enable pointer-events for interactive panel elements */
#panel-layer .hud,
#panel-layer .room-entry-overlay,
#panel-layer .dialogue-panel,
#panel-layer .taskboard-overlay,
#panel-layer .review-panel,
#panel-layer .kg-panel,
#panel-layer .prune-panel {
  pointer-events: all;
}
```

- [ ] **Step 5: Run App tests to verify they pass**

```bash
cd frontend && npx vitest run src/App.test.tsx
```
Expected: PASS — 3 tests

- [ ] **Step 6: Run the full test suite**

```bash
cd frontend && npx vitest run
```
Expected: ALL PASS — 13 prior tests + 34 new tests = 47 tests total, 0 failures

- [ ] **Step 7: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 0 errors

- [ ] **Step 8: Commit**

```bash
cd frontend && git add src/App.tsx src/App.css src/App.test.tsx
git commit -m "feat: wire all panels into App with panel state and visitor welcome page"
```

---

### Task 8: Integration Smoke Test

**Files:** None — manual verification only.

Context: Start the dev server and verify the game world with panels in a real browser. This step cannot be automated — visual appearance, SSE streaming, and Phaser-React interaction require a human to confirm.

- [ ] **Step 1: Start the dev server**

```bash
cd frontend && npm run dev
```
Open `http://localhost:3000` in a browser.

- [ ] **Step 2: Verify visitor flow**

1. Open `http://localhost:3000` — WelcomePage should appear with warm parchment card
2. Confirm name "明翰", all 4 room entries are visible
3. Click "▶ 进入空间" — WelcomePage fades away, Phaser game world loads
4. Player can move with WASD. HUD shows "👤 明翰的空间" on left.

- [ ] **Step 3: Verify owner flow**

Set `VITE_PRIVATE_KEY=testkey` in `frontend/.env`, then open `http://localhost:3000?key=testkey`.

1. Game loads directly (no WelcomePage)
2. HUD shows "📋 任务板" button and "⚙" settings icon
3. Walk to the taskboard object, press E — TaskboardPanel overlay appears
4. If backend is running (`uvicorn api.main:app`), review/prune counts load correctly
5. Click "蓄水池待审批" → ReviewPanel opens, back button → TaskboardPanel returns
6. Click "浏览认知图谱" → KGPanel opens with tabs
7. Click "节点老化提醒" → PrunePanel opens with stats grid

- [ ] **Step 4: Verify dialogue panel**

1. As visitor or owner, walk to the 赛博明翰 NPC, press E
2. DialoguePanel appears at bottom of screen
3. Type a message and press Enter or click "发送"
4. If backend is running: streaming text appears with blinking ▌ cursor, then settles
5. Click "↑ 历史" → history expands upward, messages visible
6. Click "↓ 收起" → history collapses back
7. Click "×" → panel closes, player movement resumes

- [ ] **Step 5: Final test run to confirm zero regressions**

```bash
cd frontend && npx vitest run && npx tsc --noEmit
```
Expected: all tests pass, zero type errors

---

## Self-Review

### Spec coverage

| Spec section | Covered by |
|---|---|
| §4 访客欢迎页 (名片 B2 layout) | Task 1 WelcomePage |
| §5.1 对话框 (RPG bottom bar, SSE, history expand, reflection badge) | Task 2 DialoguePanel |
| §5.2 任务板 汇总入口 (3 item types) | Task 3 TaskboardPanel (2 active types + KG browse row) |
| §5.3 审批面板 Y/N/S/Q | Task 4 ReviewPanel |
| §5.4 KG 浏览 (tabs, node cards, expand) | Task 5 KGPanel |
| §5.5 Prune 老化管理 (stats, archive/boost/skip) | Task 6 PrunePanel |
| §3 权限模型 (owner-only panels hidden from visitor) | Task 7 App.tsx `isOwner` gates |
| App wiring | Task 7 App.tsx |

**Gap note:** §5.2 spec lists "反刍新模式" (reflection patterns) as the third row. There is no dedicated backend endpoint for reflection patterns yet. TaskboardPanel shows two rows (审批 + 老化) plus a KG browse shortcut. This matches what the backend currently supports and avoids a YAGNI violation.

### Placeholder scan

None — all tasks have complete code with no TBD or TODO comments.

### Type consistency

| Symbol | Defined in | Used consistently in |
|---|---|---|
| `ReviewItem` | `api/client.ts` | ReviewPanel.tsx, TaskboardPanel.test.tsx |
| `KGNode` | `api/client.ts` | KGPanel.tsx, PrunePanel.tsx |
| `PruneStats`, `PruneCandidate` | `api/client.ts` | PrunePanel.tsx, TaskboardPanel.tsx |
| `DecideRequest` | `api/client.ts` | ReviewPanel.tsx (via `decideReviewItem`) |
| `DialoguePanelProps` | DialoguePanel.tsx | App.tsx renders it |
| `TaskboardPanelProps.onNavigate` | `(panel: 'review' \| 'kg' \| 'prune') => void` | App.tsx passes `(p) => setActivePanel({ id: p })` ✓ |
| `ActivePanel` union ids | `'dialogue'\|'taskboard'\|'review'\|'kg'\|'prune'` | Matches all panel ids in EventBus handlers ✓ |
| `cyber:panel:opened/closed` | eventbus.ts | All panels dispatch in useEffect ✓ |
