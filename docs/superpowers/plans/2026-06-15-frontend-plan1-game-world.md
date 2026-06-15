# 赛博明翰 Frontend — Plan 1: Foundation + Game World

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the React+Vite+TypeScript frontend shell, port all existing Phaser game code to TypeScript, and wire up HUD + room transitions — producing a fully playable game world before any functional panels are built.

**Architecture:** Vite+React provides the HTML shell and panel overlay layer; Phaser 3 renders the game world in a canvas mounted via `PhaserGame.tsx`; the two layers communicate exclusively through typed CustomEvents (EventBus on `window`). Owner auth is determined by `?key=` URL param matching `VITE_PRIVATE_KEY` env var.

**Tech Stack:** React 18, Vite 5, TypeScript 5, Phaser 3.80, Vitest + @testing-library/react

**Plan boundary:** This plan ends with a working game world and HUD. **Plan 2** (to follow) covers all functional panels: Dialogue, Taskboard, Review, KG, Prune, and the visitor welcome page.

**Source reference:** `frontend-old/` — the raw-JS frontend being replaced. The game layer logic is ported nearly 1:1; only panels and HUD get redesigned.

---

## File Map

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── .env                          # VITE_PRIVATE_KEY=<secret>
├── public/
│   └── assets/                   # Copied from root assets/
│       ├── player.png
│       ├── npc_cyber_v1.png
│       ├── npc_health.png
│       ├── obj-taskboard-normal.png
│       ├── obj-taskboard-active.png
│       └── tileset-placeholder.png
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── App.css
    ├── test-setup.ts
    ├── styles/
    │   └── tokens.css
    ├── eventbus.ts
    ├── api/
    │   └── client.ts
    ├── contexts/
    │   └── AuthContext.tsx
    └── game/
    │   ├── PhaserGame.tsx
    │   ├── config.ts
    │   ├── colors.ts
    │   ├── roomConfig.ts
    │   ├── scenes/
    │   │   ├── WorldScene.ts
    │   │   ├── GymScene.ts
    │   │   ├── OfficeScene.ts
    │   │   └── StudyScene.ts
    │   └── objects/
    │       ├── Player.ts
    │       ├── NPC.ts
    │       └── TriggerSystem.ts
    └── components/
        ├── HUD.tsx
        ├── HUD.css
        ├── HUD.test.tsx
        └── panels/
            ├── RoomEntryPrompt.tsx
            ├── RoomEntryPrompt.css
            └── RoomEntryPrompt.test.tsx
```

---

## Task 1: Archive old frontend + scaffold Vite project

**Files:**
- Archive: `frontend/` → `frontend-old/`
- Create: `frontend/` (Vite React TS scaffold)
- Create: `frontend/public/assets/` (copy existing assets)

- [ ] **Step 1: Archive old frontend**

```bash
mv frontend frontend-old
```

- [ ] **Step 2: Scaffold Vite React TS project**

```bash
npm create vite@latest frontend -- --template react-ts
```

Expected output includes: `✔ Project created` and `cd frontend` instructions.

- [ ] **Step 3: Install dependencies**

```bash
cd frontend && npm install && npm install phaser
npm install -D vitest @testing-library/react @testing-library/jest-dom @vitest/ui jsdom @types/node
```

- [ ] **Step 4: Copy placeholder assets**

```bash
cp ../assets/player.png           public/assets/
cp ../assets/npc_cyber_v1.png     public/assets/
cp ../assets/npc_cyber_v2.png     public/assets/
cp ../assets/npc_cyber_v3.png     public/assets/
cp ../assets/npc_health.png       public/assets/
cp ../assets/obj-taskboard-normal.png public/assets/
cp ../assets/obj-taskboard-active.png public/assets/
cp ../assets/tileset-placeholder.png  public/assets/
```

- [ ] **Step 5: Verify scaffold runs**

```bash
npm run dev
```

Expected: Vite dev server starts on `http://localhost:5173`, browser shows React default page.

- [ ] **Step 6: Commit scaffold**

```bash
git add frontend/ frontend-old/
git commit -m "chore: scaffold React+Vite+TS frontend, archive old raw-JS"
```

---

## Task 2: Configure Vite + TypeScript + test setup

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.json`
- Create: `frontend/src/test-setup.ts`
- Create: `frontend/.env`

- [ ] **Step 1: Update `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 3000 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
});
```

- [ ] **Step 2: Update `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals"]
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `frontend/src/test-setup.ts`**

```typescript
import '@testing-library/jest-dom';
```

- [ ] **Step 4: Create `frontend/.env`**

```
VITE_PRIVATE_KEY=your-secret-key-here
```

Replace `your-secret-key-here` with any string. Must match the `PRIVATE_KEY` env var used when starting the FastAPI backend.

- [ ] **Step 5: Run tests to confirm setup works**

```bash
npm run test
```

Expected: no test files found yet, exits cleanly.

- [ ] **Step 6: Commit**

```bash
git add frontend/vite.config.ts frontend/tsconfig.json frontend/src/test-setup.ts frontend/.env
git commit -m "chore: configure Vite port, TypeScript strict mode, Vitest jsdom"
```

---

## Task 3: CSS design tokens

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Modify: `frontend/index.html` (add Google Fonts)

- [ ] **Step 1: Create `frontend/src/styles/tokens.css`**

```css
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Noto+Sans+Mono:wght@400;700&display=swap');

:root {
  /* Panel layer — warm parchment */
  --panel-bg:        #c8a060;
  --panel-bg-card:   #b89050;
  --panel-border:    #6b3a10;
  --panel-shadow:    #1a0800;
  --panel-title-bg:  #8b6020;
  --panel-text:      #2c1608;
  --panel-text-dim:  #6b3a10;
  --panel-gold:      #f0d090;
  --panel-mid-bg:    #a07840;

  /* KG semantic colors */
  --color-id:        #e05c5c;
  --color-ego:       #3fb950;
  --color-superego:  #f0a500;

  /* Game world layer — dark (Phaser uses hex constants directly) */
  --game-bg:         #0d1117;
  --game-card:       #161b22;
  --game-border:     #30363d;
  --game-text:       #c9d1d9;

  /* Typography */
  --font-pixel: 'Press Start 2P', monospace;
  --font-mono:  'Noto Sans Mono', 'Courier New', monospace;

  /* Pixel UI constraints */
  --border-width:  3px;
  --pixel-shadow:  4px 4px 0 #1a0800;
  --border-radius: 0px;
}

*, *::before, *::after {
  box-sizing: border-box;
  border-radius: 0 !important;
  image-rendering: pixelated;
}

body {
  margin: 0;
  overflow: hidden;
  background: var(--game-bg);
  font-family: var(--font-mono);
}

/* Pixel button base */
.btn-pixel {
  font-family: var(--font-mono);
  font-size: 8px;
  border: var(--border-width) solid var(--panel-border);
  background: var(--panel-bg-card);
  color: var(--panel-text);
  padding: 5px 10px;
  cursor: pointer;
  box-shadow: var(--pixel-shadow);
}
.btn-pixel:hover { filter: brightness(1.1); }
.btn-pixel:active { transform: translate(2px, 2px); box-shadow: 2px 2px 0 var(--panel-shadow); }
```

- [ ] **Step 2: Update `frontend/index.html`**

```html
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>赛博明翰</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

(Google Fonts is imported inside `tokens.css` via `@import`, no `<link>` tag needed.)

- [ ] **Step 3: Import tokens in `frontend/src/main.tsx`** (will be updated again in Task 17; for now just check import compiles)

Add `import './styles/tokens.css';` to `main.tsx` after the Vite-generated content.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/index.html frontend/src/main.tsx
git commit -m "feat: add warm parchment CSS design tokens"
```

---

## Task 4: EventBus module

**Files:**
- Create: `frontend/src/eventbus.ts`
- Create: `frontend/src/eventbus.test.ts`

- [ ] **Step 1: Write failing test**

Create `frontend/src/eventbus.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { dispatch, listen } from './eventbus';

describe('eventbus', () => {
  it('dispatches and receives a typed event', () => {
    const handler = vi.fn();
    const off = listen('cyber:scene:changed', handler);
    dispatch('cyber:scene:changed', { sceneKey: 'WorldScene', roomName: '中央区' });
    expect(handler).toHaveBeenCalledWith({ sceneKey: 'WorldScene', roomName: '中央区' });
    off();
  });

  it('off() removes the listener', () => {
    const handler = vi.fn();
    const off = listen('cyber:notification:badge', handler);
    off();
    dispatch('cyber:notification:badge', { count: 3 });
    expect(handler).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
npm run test -- eventbus
```

Expected: FAIL — `eventbus` module not found.

- [ ] **Step 3: Create `frontend/src/eventbus.ts`**

```typescript
export type CyberEventDetail = {
  'cyber:npc:interact':       { npcId: string; npcName: string };
  'cyber:object:interact':    { objectId: string; contextHint?: string };
  'cyber:door:approach':      { targetScene: string; roomName: string; modeDescription: string };
  'cyber:scene:changed':      { sceneKey: string; roomName: string };
  'cyber:notification:badge': { count: number };
  'cyber:panel:opened':       { panelId: string };
  'cyber:panel:closed':       { panelId: string };
  'cyber:door:confirmed':     { targetScene: string };
  'cyber:door:cancelled':     Record<string, never>;
  'cyber:review:done':        { processedCount: number };
};

export function dispatch<K extends keyof CyberEventDetail>(
  name: K,
  detail: CyberEventDetail[K],
): void {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

export function listen<K extends keyof CyberEventDetail>(
  name: K,
  handler: (detail: CyberEventDetail[K]) => void,
): () => void {
  const fn = (e: Event) => handler((e as CustomEvent<CyberEventDetail[K]>).detail);
  window.addEventListener(name, fn);
  return () => window.removeEventListener(name, fn);
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npm run test -- eventbus
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/eventbus.ts frontend/src/eventbus.test.ts
git commit -m "feat: add typed EventBus module"
```

---

## Task 5: API client

**Files:**
- Create: `frontend/src/api/client.ts`

No unit tests for the client — it wraps `fetch`, which is an external system boundary. Integration tested in Task 18.

- [ ] **Step 1: Create `frontend/src/api/client.ts`**

```typescript
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
  onReflection: (triggered: boolean) => void,
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
    } catch { return; }
    if (!res.ok || !res.body) return;

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
          const evt = JSON.parse(line.slice(6)) as { type: string; content?: string; fullText?: string; triggered?: boolean };
          if (evt.type === 'token' && evt.content)     onToken(evt.content);
          if (evt.type === 'done'  && evt.fullText)    onDone(evt.fullText);
          if (evt.type === 'reflection')                onReflection(evt.triggered ?? false);
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
```

- [ ] **Step 2: Confirm TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add TypeScript API client"
```

---

## Task 6: Auth context

**Files:**
- Create: `frontend/src/contexts/AuthContext.tsx`
- Create: `frontend/src/contexts/AuthContext.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/src/contexts/AuthContext.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

function ShowAuth() {
  const { isOwner, privateKey } = useAuth();
  return <div data-testid="auth">{isOwner ? 'owner' : 'visitor'}:{privateKey}</div>;
}

describe('AuthContext', () => {
  // jsdom URL is 'http://localhost/' with no search params, so no ?key= is present.
  // VITE_PRIVATE_KEY is empty in test env (not set in .env.test), so isOwner is always false here.
  it('defaults to visitor when no URL key param', () => {
    render(<AuthProvider><ShowAuth /></AuthProvider>);
    expect(screen.getByTestId('auth').textContent).toBe('visitor:');
  });
});
```

- [ ] **Step 2: Run to see failure**

```bash
npm run test -- AuthContext
```

Expected: FAIL — `AuthContext` module not found.

- [ ] **Step 3: Create `frontend/src/contexts/AuthContext.tsx`**

```typescript
import { createContext, useContext, useMemo, type ReactNode } from 'react';

export interface AuthContextValue {
  isOwner:    boolean;
  privateKey: string;
}

export const AuthContext = createContext<AuthContextValue>({ isOwner: false, privateKey: '' });

export function AuthProvider({ children }: { children: ReactNode }) {
  const value = useMemo<AuthContextValue>(() => {
    const params  = new URLSearchParams(window.location.search);
    const urlKey  = params.get('key') ?? '';
    const envKey  = (import.meta.env.VITE_PRIVATE_KEY as string | undefined) ?? '';
    const isOwner = Boolean(envKey && urlKey === envKey);
    return { isOwner, privateKey: urlKey };
  }, []);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npm run test -- AuthContext
```

Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/
git commit -m "feat: add AuthContext for owner/visitor mode detection"
```

---

## Task 7: Phaser config + colors + roomConfig

**Files:**
- Create: `frontend/src/game/config.ts`
- Create: `frontend/src/game/colors.ts`
- Create: `frontend/src/game/roomConfig.ts`

These are small, no unit tests (they contain constants and Phaser-dependent imports).

- [ ] **Step 1: Create `frontend/src/game/config.ts`**

```typescript
export const GAME_WIDTH  = 720;
export const GAME_HEIGHT = 450;
export const GAME_ZOOM   = 2;
```

- [ ] **Step 2: Create `frontend/src/game/colors.ts`**

```typescript
export const COLORS = {
  BG:       0x0d1117,
  CARD_BG:  0x161b22,
  BORDER:   0x30363d,
  TEXT:     0xc9d1d9,
  ID:       0xe05c5c,
  EGO:      0x3fb950,
  SUPEREGO: 0xf0a500,
} as const;
```

- [ ] **Step 3: Create `frontend/src/game/roomConfig.ts`**

```typescript
import type Phaser from 'phaser';

export interface RoomConfig {
  key:        string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sceneClass: new (...args: any[]) => Phaser.Scene;
  label:      string;
  phase:      number;
}

// Scenes imported lazily to avoid circular deps; populated in main Phaser setup.
// roomConfig.ts is the canonical list — add Phase 2 rooms here only.
import { WorldScene }  from './scenes/WorldScene';
import { GymScene }    from './scenes/GymScene';
import { OfficeScene } from './scenes/OfficeScene';
import { StudyScene }  from './scenes/StudyScene';

export const ROOM_CONFIG: RoomConfig[] = [
  { key: 'WorldScene',  sceneClass: WorldScene,  label: '中央区', phase: 1 },
  { key: 'GymScene',    sceneClass: GymScene,    label: '健身房', phase: 1 },
  { key: 'OfficeScene', sceneClass: OfficeScene, label: '办公室', phase: 2 },
  { key: 'StudyScene',  sceneClass: StudyScene,  label: '学习室', phase: 2 },
];
```

- [ ] **Step 4: Confirm TypeScript compiles (after game objects are created in later tasks; for now skip)**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/game/config.ts frontend/src/game/colors.ts frontend/src/game/roomConfig.ts
git commit -m "feat: add Phaser game constants (config, colors, roomConfig)"
```

---

## Task 8: TriggerSystem

**Files:**
- Create: `frontend/src/game/objects/TriggerSystem.ts`

- [ ] **Step 1: Create `frontend/src/game/objects/TriggerSystem.ts`**

```typescript
import Phaser from 'phaser';
import { dispatch } from '../../eventbus';

export interface TriggerZone {
  id:               string;
  kind:             'proximity' | 'interact';
  rect:             Phaser.Geom.Rectangle;
  phase?:           number;
  type:             string;
  targetScene?:     string;
  roomName?:        string;
  modeDescription?: string;
  objectId?:        string;
  contextHint?:     string;
  npcId?:           string;
  npcName?:         string;
  onTrigger?:       () => void;
}

export class TriggerSystem {
  private zones:     TriggerZone[] = [];
  private insideIds: Set<string>   = new Set();
  private eKey:      Phaser.Input.Keyboard.Key;

  constructor(private scene: Phaser.Scene) {
    this.eKey = scene.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.E);
  }

  add(zone: TriggerZone): this { this.zones.push(zone); return this; }

  update(playerX: number, playerY: number): void {
    for (const zone of this.zones) {
      const inside = Phaser.Geom.Rectangle.Contains(zone.rect, playerX, playerY);

      if (zone.kind === 'proximity') {
        if (inside && !this.insideIds.has(zone.id)) {
          this.insideIds.add(zone.id);
          this.fireProximity(zone);
        } else if (!inside) {
          this.insideIds.delete(zone.id);
        }
      } else if (zone.kind === 'interact' && inside) {
        if (Phaser.Input.Keyboard.JustDown(this.eKey)) {
          this.fireInteract(zone);
        }
      }
    }
  }

  private fireProximity(zone: TriggerZone): void {
    if (zone.onTrigger) { zone.onTrigger(); return; }
    if ((zone.phase ?? 1) > 1) { this.showHint('即将开放'); return; }
    if (zone.type.startsWith('door_to')) {
      dispatch('cyber:door:approach', {
        targetScene:     zone.targetScene!,
        roomName:        zone.roomName!,
        modeDescription: zone.modeDescription ?? '',
      });
    }
  }

  private fireInteract(zone: TriggerZone): void {
    if (zone.onTrigger) { zone.onTrigger(); return; }
    if (zone.type === 'npc') {
      dispatch('cyber:npc:interact', { npcId: zone.npcId!, npcName: zone.npcName! });
    } else if (zone.type === 'object') {
      dispatch('cyber:object:interact', { objectId: zone.objectId!, contextHint: zone.contextHint });
    }
  }

  private showHint(msg: string): void {
    const { width, height } = this.scene.cameras.main;
    const t = this.scene.add.text(width / 2, height / 2 - 60, msg, {
      fontSize: '9px', color: '#f0a500', fontFamily: 'monospace',
      backgroundColor: '#161b22', padding: { x: 8, y: 5 },
    }).setOrigin(0.5).setDepth(10);
    this.scene.time.delayedCall(1800, () => t.destroy());
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/game/objects/TriggerSystem.ts
git commit -m "feat: port TriggerSystem to TypeScript"
```

---

## Task 9: Player

**Files:**
- Create: `frontend/src/game/objects/Player.ts`

- [ ] **Step 1: Create `frontend/src/game/objects/Player.ts`**

```typescript
import Phaser from 'phaser';
import { COLORS } from '../colors';

const SPEED = 80;

const DIR_COLOR: Record<string, number> = {
  idle:       COLORS.EGO,
  walk_down:  0x5fd96a,
  walk_up:    0x2da83b,
  walk_left:  0x1e8f2e,
  walk_right: 0x7fff8a,
};

export class Player {
  private inputEnabled = true;
  private direction    = 'idle';
  private sprite:      Phaser.GameObjects.Rectangle;
  private body:        Phaser.Physics.Arcade.Body;
  private cursors:     Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd:        Record<string, Phaser.Input.Keyboard.Key>;

  constructor(scene: Phaser.Scene, x: number, y: number) {
    this.sprite = scene.add.rectangle(x, y, 14, 22, COLORS.EGO);
    scene.physics.add.existing(this.sprite);
    this.body = this.sprite.body as Phaser.Physics.Arcade.Body;
    this.body.setCollideWorldBounds(true);

    this.cursors = scene.input.keyboard!.createCursorKeys();
    this.wasd = scene.input.keyboard!.addKeys({
      up:    Phaser.Input.Keyboard.KeyCodes.W,
      down:  Phaser.Input.Keyboard.KeyCodes.S,
      left:  Phaser.Input.Keyboard.KeyCodes.A,
      right: Phaser.Input.Keyboard.KeyCodes.D,
    }) as Record<string, Phaser.Input.Keyboard.Key>;
  }

  update(): void {
    if (!this.inputEnabled) { this.body.setVelocity(0, 0); return; }

    let vx = 0, vy = 0;
    if (this.cursors.left.isDown  || this.wasd['left'].isDown)  vx = -SPEED;
    if (this.cursors.right.isDown || this.wasd['right'].isDown) vx =  SPEED;
    if (this.cursors.up.isDown    || this.wasd['up'].isDown)    vy = -SPEED;
    if (this.cursors.down.isDown  || this.wasd['down'].isDown)  vy =  SPEED;
    if (vx !== 0 && vy !== 0) { vx *= 0.707; vy *= 0.707; }

    this.body.setVelocity(vx, vy);

    let dir = 'idle';
    if      (vx < 0) dir = 'walk_left';
    else if (vx > 0) dir = 'walk_right';
    else if (vy < 0) dir = 'walk_up';
    else if (vy > 0) dir = 'walk_down';

    if (dir !== this.direction) {
      this.direction = dir;
      this.sprite.setFillStyle(DIR_COLOR[dir]);
    }
  }

  enableInput():  void { this.inputEnabled = true; }
  disableInput(): void { this.inputEnabled = false; this.body.setVelocity(0, 0); }

  get x(): number { return this.sprite.x; }
  get y(): number { return this.sprite.y; }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/game/objects/Player.ts
git commit -m "feat: port Player to TypeScript"
```

---

## Task 10: NPC

**Files:**
- Create: `frontend/src/game/objects/NPC.ts`

- [ ] **Step 1: Create `frontend/src/game/objects/NPC.ts`**

```typescript
import Phaser from 'phaser';
import { COLORS } from '../colors';
import type { TriggerSystem } from './TriggerSystem';

export interface NPCOpts {
  npcId:          string;
  npcName:        string;
  spriteKey:      string;
  x:              number;
  y:              number;
  triggerSystem?: TriggerSystem;
}

export class NPC {
  readonly npcId:   string;
  readonly npcName: string;
  private sprite:   Phaser.GameObjects.Rectangle;
  private label:    Phaser.GameObjects.Text;

  constructor(scene: Phaser.Scene, opts: NPCOpts) {
    const { npcId, npcName, x, y, triggerSystem } = opts;
    this.npcId   = npcId;
    this.npcName = npcName;

    this.sprite = scene.add.rectangle(x, y, 16, 24, COLORS.ID);
    this.label  = scene.add.text(x, y - 18, npcName, {
      fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace',
    }).setOrigin(0.5);

    scene.tweens.add({
      targets: this.sprite, alpha: { from: 0.65, to: 1 },
      duration: 750, yoyo: true, repeat: -1, ease: 'Linear',
    });

    if (triggerSystem) {
      triggerSystem.add({
        id: `npc_${npcId}`, kind: 'interact', type: 'npc',
        rect: new Phaser.Geom.Rectangle(x - 24, y - 26, 48, 52),
        npcId, npcName,
      });
    }
  }

  destroy(): void {
    this.sprite.destroy();
    this.label.destroy();
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/game/objects/NPC.ts
git commit -m "feat: port NPC to TypeScript"
```

---

## Task 11: WorldScene

**Files:**
- Create: `frontend/src/game/scenes/WorldScene.ts`

- [ ] **Step 1: Create `frontend/src/game/scenes/WorldScene.ts`**

```typescript
import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { NPC } from '../objects/NPC';
import { TriggerSystem } from '../objects/TriggerSystem';
import { listen } from '../../eventbus';
import type { CyberEventDetail } from '../../eventbus';

const SPAWN_X = 360;
const SPAWN_Y = 225;

export class WorldScene extends Phaser.Scene {
  private player!:       Player;
  private triggers!:     TriggerSystem;
  private taskboard!:    Phaser.GameObjects.Rectangle;
  private transitioning  = false;
  private offListeners:  Array<() => void> = [];

  constructor() { super({ key: 'WorldScene' }); }

  create(): void {
    this.drawLayout();
    this.taskboard = this.add.rectangle(310, 190, 24, 16, COLORS.SUPEREGO, 0.7);
    this.add.text(298, 195, '[任务板]', { fontSize: '6px', color: '#0d1117', fontFamily: 'monospace' });

    this.player = new Player(this, SPAWN_X, SPAWN_Y);
    this.setupTriggers();

    new NPC(this, {
      npcId: 'cyber_minghan', npcName: '赛博明翰',
      spriteKey: 'npc_cyber_v1', x: 400, y: 235,
      triggerSystem: this.triggers,
    });

    this.setupEventBus();
    this.events.on('shutdown', this.teardownEventBus, this);

    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      this.dispatchSceneChanged();
      void this.queryNotifications();
    });
  }

  update(): void {
    this.player.update();
    this.triggers.update(this.player.x, this.player.y);
  }

  private drawLayout(): void {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG);
    gfx.fillRect(0, 0, 720, 450);
    gfx.fillStyle(COLORS.CARD_BG);
    gfx.fillRect(240, 150, 240, 150);
    gfx.lineStyle(1, COLORS.BORDER);
    gfx.strokeRect(240, 150, 240, 150);
    this.add.text(288, 205, '中央活动区', { fontSize: '8px', color: '#c9d1d9', fontFamily: 'monospace' });
    this.drawRoom(gfx,  20,  20, 150, 90, COLORS.EGO,      '健身房\n[GYM]',    true);
    this.drawRoom(gfx, 550,  20, 150, 90, COLORS.SUPEREGO,  '学习室\n[STUDY]',  false);
    this.drawRoom(gfx,  20, 340, 150, 90, COLORS.ID,        '办公室\n[OFFICE]', false);
    this.drawRoom(gfx, 550, 340, 150, 90, COLORS.BORDER,    '[预留]',           false);
  }

  private drawRoom(gfx: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number,
                   color: number, label: string, phase1: boolean): void {
    gfx.fillStyle(color, phase1 ? 0.2 : 0.08);
    gfx.fillRect(x, y, w, h);
    gfx.lineStyle(1, color, phase1 ? 0.8 : 0.35);
    gfx.strokeRect(x, y, w, h);
    this.add.text(x + 5, y + 5, label, { fontSize: '7px', color: '#c9d1d9', fontFamily: 'monospace' });
    const doorX = x + w / 2 - 12;
    const doorY = (y + h / 2) > 225 ? y : y + h - 8;
    gfx.fillStyle(color, phase1 ? 0.6 : 0.2);
    gfx.fillRect(doorX, doorY, 24, 8);
  }

  private setupTriggers(): void {
    const R = Phaser.Geom.Rectangle;
    this.triggers = new TriggerSystem(this);
    this.triggers
      .add({ id: 'door_gym',     kind: 'proximity', phase: 1, type: 'door_to_gym',
             rect: new R(63,  95,  64, 28), targetScene: 'GymScene',
             roomName: '健身房', modeDescription: '进入健康管家模式' })
      .add({ id: 'door_study',   kind: 'proximity', phase: 2, type: 'door_to_study',
             rect: new R(593, 95,  64, 28), targetScene: 'StudyScene', roomName: '学习室' })
      .add({ id: 'door_office',  kind: 'proximity', phase: 2, type: 'door_to_office',
             rect: new R(63,  333, 64, 28), targetScene: 'OfficeScene', roomName: '办公室' })
      .add({ id: 'obj_taskboard', kind: 'interact', type: 'object',
             rect: new R(294, 180, 40, 24), objectId: 'taskboard' });
  }

  private setupEventBus(): void {
    this.offListeners = [
      listen('cyber:panel:opened',   ()  => this.player.disableInput()),
      listen('cyber:panel:closed',   ()  => { if (!this.transitioning) this.player.enableInput(); }),
      listen('cyber:door:confirmed', (e) => this.onDoorConfirmed(e)),
      listen('cyber:door:cancelled', ()  => { /* panel:closed already re-enables input */ }),
      listen('cyber:review:done',    ()  => this.onReviewDone()),
    ];
  }

  private teardownEventBus(): void {
    this.offListeners.forEach(off => off());
    this.offListeners = [];
  }

  private onDoorConfirmed({ targetScene }: CyberEventDetail['cyber:door:confirmed']): void {
    this.transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.transitioning = false;
      this.scene.start(targetScene);
    });
  }

  private onReviewDone(): void {
    this.tweens.add({
      targets: this.taskboard, alpha: { from: 1, to: 0.15 },
      duration: 120, yoyo: true, repeat: 3,
      onComplete: () => { this.taskboard.setAlpha(0.7); void this.queryNotifications(); },
    });
  }

  private async queryNotifications(): Promise<void> {
    try {
      const res = await fetch('http://localhost:8000/api/notifications');
      if (!res.ok) return;
      const { count = 0 } = (await res.json()) as { count: number };
      window.dispatchEvent(new CustomEvent('cyber:notification:badge', { detail: { count } }));
      this.setTaskboardState(count > 0);
    } catch { /* backend offline — silently skip */ }
  }

  private setTaskboardState(active: boolean): void {
    this.taskboard.setFillStyle(COLORS.SUPEREGO, active ? 1.0 : 0.5);
    if (active) {
      this.tweens.add({
        targets: this.taskboard,
        scaleX: { from: 1, to: 1.4 }, scaleY: { from: 1, to: 1.4 },
        duration: 180, yoyo: true,
      });
    }
  }

  private dispatchSceneChanged(): void {
    window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
      detail: { sceneKey: 'WorldScene', roomName: '中央区' },
    }));
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/game/scenes/WorldScene.ts
git commit -m "feat: port WorldScene to TypeScript"
```

---

## Task 12: GymScene

**Files:**
- Create: `frontend/src/game/scenes/GymScene.ts`

- [ ] **Step 1: Create `frontend/src/game/scenes/GymScene.ts`**

```typescript
import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { NPC } from '../objects/NPC';
import { TriggerSystem } from '../objects/TriggerSystem';
import { listen } from '../../eventbus';

const SPAWN_X = 360;
const SPAWN_Y = 380;

export class GymScene extends Phaser.Scene {
  private player!:       Player;
  private triggers!:     TriggerSystem;
  private transitioning  = false;
  private offListeners:  Array<() => void> = [];

  constructor() { super({ key: 'GymScene' }); }

  create(): void {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG);    gfx.fillRect(0, 0, 720, 450);
    gfx.fillStyle(0x1a2a1a);     gfx.fillRect(40, 40, 640, 380);
    gfx.lineStyle(2, COLORS.EGO, 0.6); gfx.strokeRect(40, 40, 640, 380);

    this.add.text(300, 50, '🏋️ 健身房', { fontSize: '10px', color: '#c9d1d9', fontFamily: 'monospace' });

    // Weight calendar object placeholder
    this.add.rectangle(180, 200, 48, 40, COLORS.EGO, 0.5);
    this.add.text(155, 225, '[体重日历]', { fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace' });

    // Training log object placeholder
    this.add.rectangle(320, 200, 16, 32, COLORS.EGO, 0.4);
    this.add.text(307, 225, '[训练本]', { fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace' });

    // Exit indicator
    this.add.rectangle(360, 420, 48, 12, COLORS.EGO, 0.7);
    this.add.text(340, 426, '[← 出口]', { fontSize: '6px', color: '#c9d1d9', fontFamily: 'monospace' });

    this.player   = new Player(this, SPAWN_X, SPAWN_Y);
    this.triggers = new TriggerSystem(this);
    const R = Phaser.Geom.Rectangle;

    new NPC(this, {
      npcId: 'health_coach', npcName: '健康管家',
      spriteKey: 'npc_health', x: 500, y: 200,
      triggerSystem: this.triggers,
    });

    this.triggers
      .add({ id: 'weight_cal',   kind: 'interact', type: 'object',
             rect: new R(158, 178, 52, 48),
             objectId: 'weight_calendar', contextHint: '用户想查看体重趋势' })
      .add({ id: 'training_log', kind: 'interact', type: 'object',
             rect: new R(308, 182, 28, 48),
             objectId: 'training_log', contextHint: '用户想回顾训练记录' })
      .add({ id: 'exit_to_world', kind: 'proximity', type: 'exit',
             rect: new R(336, 412, 64, 24),
             onTrigger: () => { this.exitToWorld(); } });

    this.offListeners = [
      listen('cyber:panel:opened', () => this.player.disableInput()),
      listen('cyber:panel:closed', () => { if (!this.transitioning) this.player.enableInput(); }),
    ];
    this.events.on('shutdown', () => { this.offListeners.forEach(off => off()); }, this);

    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
        detail: { sceneKey: 'GymScene', roomName: '健身房' },
      }));
    });
  }

  update(): void {
    this.player.update();
    this.triggers.update(this.player.x, this.player.y);
  }

  private exitToWorld(): void {
    if (this.transitioning) return;
    this.transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.transitioning = false;
      this.scene.start('WorldScene');
    });
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/game/scenes/GymScene.ts
git commit -m "feat: port GymScene to TypeScript"
```

---

## Task 13: OfficeScene + StudyScene stubs

**Files:**
- Create: `frontend/src/game/scenes/OfficeScene.ts`
- Create: `frontend/src/game/scenes/StudyScene.ts`

These are Phase 2 — unreachable in Phase 1 (door trigger shows "即将开放"). Minimal stubs only.

- [ ] **Step 1: Create `frontend/src/game/scenes/OfficeScene.ts`**

```typescript
import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { listen } from '../../eventbus';

export class OfficeScene extends Phaser.Scene {
  private player!:      Player;
  private transitioning = false;
  private offListeners: Array<() => void> = [];

  constructor() { super({ key: 'OfficeScene' }); }

  create(): void {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG); gfx.fillRect(0, 0, 720, 450);
    this.add.text(260, 180, '🚧 办公室\n即将开放', {
      fontSize: '12px', color: '#f0a500', fontFamily: 'monospace', align: 'center',
    });
    this.player = new Player(this, 360, 380);
    this.offListeners = [
      listen('cyber:panel:opened', () => this.player.disableInput()),
      listen('cyber:panel:closed', () => { if (!this.transitioning) this.player.enableInput(); }),
    ];
    this.events.on('shutdown', () => { this.offListeners.forEach(off => off()); }, this);
    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
        detail: { sceneKey: 'OfficeScene', roomName: '办公室' },
      }));
    });
  }

  update(): void {
    this.player.update();
    if (this.player.y > 420 && !this.transitioning) this.exitToWorld();
  }

  private exitToWorld(): void {
    this.transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.transitioning = false;
      this.scene.start('WorldScene');
    });
  }
}
```

- [ ] **Step 2: Create `frontend/src/game/scenes/StudyScene.ts`**

```typescript
import Phaser from 'phaser';
import { COLORS } from '../colors';
import { Player } from '../objects/Player';
import { listen } from '../../eventbus';

export class StudyScene extends Phaser.Scene {
  private player!:      Player;
  private transitioning = false;
  private offListeners: Array<() => void> = [];

  constructor() { super({ key: 'StudyScene' }); }

  create(): void {
    const gfx = this.add.graphics();
    gfx.fillStyle(COLORS.BG); gfx.fillRect(0, 0, 720, 450);
    this.add.text(260, 180, '📚 学习室\n即将开放', {
      fontSize: '12px', color: '#f0a500', fontFamily: 'monospace', align: 'center',
    });
    this.player = new Player(this, 360, 380);
    this.offListeners = [
      listen('cyber:panel:opened', () => this.player.disableInput()),
      listen('cyber:panel:closed', () => { if (!this.transitioning) this.player.enableInput(); }),
    ];
    this.events.on('shutdown', () => { this.offListeners.forEach(off => off()); }, this);
    this.cameras.main.fadeIn(300, 0, 0, 0);
    this.cameras.main.once('camerafadeincomplete', () => {
      window.dispatchEvent(new CustomEvent('cyber:scene:changed', {
        detail: { sceneKey: 'StudyScene', roomName: '学习室' },
      }));
    });
  }

  update(): void {
    this.player.update();
    if (this.player.y > 420 && !this.transitioning) this.exitToWorld();
  }

  private exitToWorld(): void {
    this.transitioning = true;
    this.player.disableInput();
    this.cameras.main.fadeOut(300, 0, 0, 0);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      this.transitioning = false;
      this.scene.start('WorldScene');
    });
  }
}
```

- [ ] **Step 3: Confirm full game TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/game/scenes/OfficeScene.ts frontend/src/game/scenes/StudyScene.ts
git commit -m "feat: add Phase 2 stub scenes (OfficeScene, StudyScene)"
```

---

## Task 14: PhaserGame React component

**Files:**
- Create: `frontend/src/game/PhaserGame.tsx`

- [ ] **Step 1: Create `frontend/src/game/PhaserGame.tsx`**

```typescript
import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
import { GAME_WIDTH, GAME_HEIGHT, GAME_ZOOM } from './config';
import { ROOM_CONFIG } from './roomConfig';

export function PhaserGame() {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef      = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;

    gameRef.current = new Phaser.Game({
      type:            Phaser.AUTO,
      width:           GAME_WIDTH,
      height:          GAME_HEIGHT,
      zoom:            GAME_ZOOM,
      pixelArt:        true,
      backgroundColor: '#0d1117',
      parent:          containerRef.current,
      physics: {
        default: 'arcade',
        arcade:  { gravity: { x: 0, y: 0 }, debug: false },
      },
      scene: ROOM_CONFIG.map(r => r.sceneClass),
    });

    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ position: 'fixed', inset: 0, zIndex: 0 }}
    />
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/game/PhaserGame.tsx
git commit -m "feat: add PhaserGame React component (Phaser 3 canvas mount)"
```

---

## Task 15: HUD component + tests

**Files:**
- Create: `frontend/src/components/HUD.tsx`
- Create: `frontend/src/components/HUD.css`
- Create: `frontend/src/components/HUD.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/HUD.test.tsx`:

```typescript
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { HUD } from './HUD';
import { AuthContext } from '../contexts/AuthContext';

// Mock eventbus
const listenMocks: Record<string, (detail: unknown) => void> = {};
vi.mock('../eventbus', () => ({
  listen: vi.fn((name: string, handler: (d: unknown) => void) => {
    listenMocks[name] = handler;
    return () => { delete listenMocks[name]; };
  }),
  dispatch: vi.fn(),
}));

const renderWithAuth = (isOwner: boolean) =>
  render(
    <AuthContext.Provider value={{ isOwner, privateKey: isOwner ? 'k' : '' }}>
      <HUD />
    </AuthContext.Provider>,
  );

describe('HUD', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders taskboard button in owner mode', () => {
    renderWithAuth(true);
    expect(screen.getByTestId('hud-taskboard-btn')).toBeInTheDocument();
    expect(screen.queryByTestId('hud-chat-btn')).toBeNull();
  });

  it('renders chat button in visitor mode', () => {
    renderWithAuth(false);
    expect(screen.getByTestId('hud-chat-btn')).toBeInTheDocument();
    expect(screen.queryByTestId('hud-taskboard-btn')).toBeNull();
  });

  it('shows visitor indicator in visitor mode', () => {
    renderWithAuth(false);
    expect(screen.getByText(/明翰的空间/)).toBeInTheDocument();
  });

  it('shows badge when notification count > 0', async () => {
    renderWithAuth(true);
    await act(async () => {
      listenMocks['cyber:notification:badge']?.({ count: 4 });
    });
    expect(screen.getByTestId('hud-badge')).toHaveTextContent('4');
  });

  it('hides badge when count is 0', async () => {
    renderWithAuth(true);
    await act(async () => {
      listenMocks['cyber:notification:badge']?.({ count: 0 });
    });
    expect(screen.queryByTestId('hud-badge')).toBeNull();
  });

  it('updates room name on scene change', async () => {
    renderWithAuth(true);
    await act(async () => {
      listenMocks['cyber:scene:changed']?.({ sceneKey: 'GymScene', roomName: '健身房' });
    });
    expect(screen.getByText(/健身房/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to confirm failure**

```bash
npm run test -- HUD
```

Expected: FAIL — `HUD` module not found.

- [ ] **Step 3: Create `frontend/src/components/HUD.tsx`**

```typescript
import { useState, useEffect } from 'react';
import { listen, dispatch } from '../eventbus';
import { useAuth } from '../contexts/AuthContext';
import './HUD.css';

export function HUD() {
  const { isOwner } = useAuth();
  const [roomName,   setRoomName]   = useState('中央活动区');
  const [badgeCount, setBadgeCount] = useState(0);

  useEffect(() => {
    const off1 = listen('cyber:scene:changed',      ({ roomName }) => setRoomName(roomName));
    const off2 = listen('cyber:notification:badge', ({ count })   => setBadgeCount(count));
    return () => { off1(); off2(); };
  }, []);

  if (isOwner) {
    return (
      <div className="hud hud--owner" data-testid="hud">
        <span className="hud-room">🏠 {roomName}</span>
        <div className="hud-right">
          <button
            className="hud-btn hud-taskboard"
            onClick={() => dispatch('cyber:object:interact', { objectId: 'taskboard' })}
            data-testid="hud-taskboard-btn"
          >
            📋 任务板
            {badgeCount > 0 && (
              <span className="hud-badge" data-testid="hud-badge">{badgeCount}</span>
            )}
          </button>
          <button className="hud-btn hud-settings">⚙</button>
        </div>
      </div>
    );
  }

  return (
    <div className="hud hud--visitor" data-testid="hud">
      <span className="hud-indicator">👤 明翰的空间</span>
      <span className="hud-room">🏠 {roomName}</span>
      <button
        className="hud-btn hud-chat"
        onClick={() => dispatch('cyber:npc:interact', { npcId: 'cyber_minghan', npcName: '赛博明翰' })}
        data-testid="hud-chat-btn"
      >
        💬 和明翰聊天
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/HUD.css`**

```css
.hud {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 28px;
  z-index: 100;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 8px;
  background: rgba(44, 22, 8, 0.93);
  border-bottom: var(--border-width) solid var(--panel-border);
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--panel-gold);
  box-shadow: 0 3px 0 var(--panel-shadow);
}
.hud-room { color: var(--panel-gold); }
.hud-indicator {
  background: var(--panel-border);
  padding: 2px 7px;
  font-size: 7px;
  color: var(--panel-bg);
}
.hud-right { margin-left: auto; display: flex; align-items: center; gap: 6px; }
.hud-btn {
  background: var(--panel-bg-card);
  border: 2px solid var(--panel-border);
  color: var(--panel-text);
  font-family: var(--font-mono);
  font-size: 8px;
  padding: 3px 7px;
  cursor: pointer;
  position: relative;
}
.hud-settings {
  background: var(--panel-border);
  color: var(--panel-bg);
  padding: 3px 6px;
}
.hud-badge {
  position: absolute;
  top: -5px; right: -5px;
  background: var(--color-id);
  color: #fff;
  font-size: 7px;
  font-weight: bold;
  width: 14px; height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #8b1a1a;
}
.hud--visitor .hud-chat {
  background: var(--panel-bg-card);
  margin-left: auto;
}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
npm run test -- HUD
```

Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/HUD.tsx frontend/src/components/HUD.css frontend/src/components/HUD.test.tsx
git commit -m "feat: add HUD component with owner/visitor modes and badge"
```

---

## Task 16: RoomEntryPrompt + tests

**Files:**
- Create: `frontend/src/components/panels/RoomEntryPrompt.tsx`
- Create: `frontend/src/components/panels/RoomEntryPrompt.css`
- Create: `frontend/src/components/panels/RoomEntryPrompt.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/panels/RoomEntryPrompt.test.tsx`:

```typescript
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RoomEntryPrompt } from './RoomEntryPrompt';

const listenMocks: Record<string, (detail: unknown) => void> = {};
const mockDispatch = vi.fn();

vi.mock('../../eventbus', () => ({
  listen: vi.fn((name: string, handler: (d: unknown) => void) => {
    listenMocks[name] = handler;
    return () => { delete listenMocks[name]; };
  }),
  dispatch: mockDispatch,
}));

describe('RoomEntryPrompt', () => {
  beforeEach(() => { vi.clearAllMocks(); mockDispatch.mockReset(); });

  it('is hidden initially', () => {
    render(<RoomEntryPrompt />);
    expect(screen.queryByTestId('room-entry')).toBeNull();
  });

  it('shows prompt on cyber:door:approach', async () => {
    render(<RoomEntryPrompt />);
    await act(async () => {
      listenMocks['cyber:door:approach']?.({
        targetScene: 'GymScene', roomName: '健身房', modeDescription: '进入健康管家模式',
      });
    });
    expect(screen.getByTestId('room-entry')).toBeInTheDocument();
    expect(screen.getByText(/健身房/)).toBeInTheDocument();
  });

  it('confirm dispatches cyber:door:confirmed and closes', async () => {
    render(<RoomEntryPrompt />);
    await act(async () => {
      listenMocks['cyber:door:approach']?.({
        targetScene: 'GymScene', roomName: '健身房', modeDescription: '',
      });
    });
    fireEvent.click(screen.getByTestId('room-entry-confirm'));
    expect(mockDispatch).toHaveBeenCalledWith('cyber:door:confirmed', { targetScene: 'GymScene' });
    expect(screen.queryByTestId('room-entry')).toBeNull();
  });

  it('cancel dispatches cyber:door:cancelled and closes', async () => {
    render(<RoomEntryPrompt />);
    await act(async () => {
      listenMocks['cyber:door:approach']?.({
        targetScene: 'GymScene', roomName: '健身房', modeDescription: '',
      });
    });
    fireEvent.click(screen.getByTestId('room-entry-cancel'));
    expect(mockDispatch).toHaveBeenCalledWith('cyber:door:cancelled', {});
    expect(screen.queryByTestId('room-entry')).toBeNull();
  });
});
```

- [ ] **Step 2: Run to confirm failure**

```bash
npm run test -- RoomEntryPrompt
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/src/components/panels/RoomEntryPrompt.tsx`**

```typescript
import { useState, useEffect } from 'react';
import { listen, dispatch } from '../../eventbus';
import './RoomEntryPrompt.css';

export function RoomEntryPrompt() {
  const [visible,      setVisible]      = useState(false);
  const [roomName,     setRoomName]     = useState('');
  const [modeDesc,     setModeDesc]     = useState('');
  const [targetScene,  setTargetScene]  = useState('');

  useEffect(() => {
    const off = listen('cyber:door:approach', ({ targetScene, roomName, modeDescription }) => {
      setTargetScene(targetScene);
      setRoomName(roomName);
      setModeDesc(modeDescription);
      setVisible(true);
      dispatch('cyber:panel:opened', { panelId: 'room-entry' });
    });
    return off;
  }, []);

  const handleConfirm = () => {
    setVisible(false);
    dispatch('cyber:door:confirmed', { targetScene });
    dispatch('cyber:panel:closed',   { panelId: 'room-entry' });
  };

  const handleCancel = () => {
    setVisible(false);
    dispatch('cyber:door:cancelled', {});
    dispatch('cyber:panel:closed',   { panelId: 'room-entry' });
  };

  if (!visible) return null;

  return (
    <div className="room-entry-overlay" data-testid="room-entry">
      <div className="room-entry-box">
        <div className="room-entry-title">进入 {roomName}</div>
        {modeDesc && <div className="room-entry-desc">{modeDesc}</div>}
        <div className="room-entry-actions">
          <button className="btn-pixel btn-confirm" onClick={handleConfirm} data-testid="room-entry-confirm">
            [Y] 进入
          </button>
          <button className="btn-pixel btn-cancel"  onClick={handleCancel}  data-testid="room-entry-cancel">
            [N] 返回
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/panels/RoomEntryPrompt.css`**

```css
.room-entry-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(26, 8, 0, 0.55);
}
.room-entry-box {
  background: var(--panel-bg);
  border: var(--border-width) solid var(--panel-border);
  box-shadow: var(--pixel-shadow);
  padding: 20px 28px;
  min-width: 260px;
  text-align: center;
  font-family: var(--font-mono);
}
.room-entry-title {
  font-size: 11px;
  color: var(--panel-text);
  margin-bottom: 6px;
  font-weight: bold;
}
.room-entry-desc {
  font-size: 8px;
  color: var(--panel-text-dim);
  margin-bottom: 14px;
}
.room-entry-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.btn-confirm {
  background: var(--color-ego);
  border-color: #1a6b20;
  color: #fff;
}
.btn-cancel {
  background: var(--panel-bg-card);
  border-color: var(--panel-border);
  color: var(--panel-text);
}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
npm run test -- RoomEntryPrompt
```

Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/panels/
git commit -m "feat: add RoomEntryPrompt component with Y/N door confirmation"
```

---

## Task 17: App shell + entry point

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/App.css`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```typescript
import { PhaserGame }       from './game/PhaserGame';
import { HUD }              from './components/HUD';
import { RoomEntryPrompt }  from './components/panels/RoomEntryPrompt';
import './styles/tokens.css';
import './App.css';

export default function App() {
  return (
    <>
      {/* Layer 0: Phaser game world (fixed, z-index 0) */}
      <PhaserGame />

      {/* Layer 1: React panel overlay (z-index 100+) */}
      <div id="panel-layer">
        <HUD />
        <RoomEntryPrompt />
        {/* Plan 2 panels will be added here: DialoguePanel, TaskboardPanel, ReviewPanel, KGPanel, PrunePanel */}
      </div>
    </>
  );
}
```

- [ ] **Step 2: Create `frontend/src/App.css`**

```css
#panel-layer {
  position: relative;
  z-index: 10;
  pointer-events: none; /* let clicks fall through to Phaser by default */
}
/* Individual panels re-enable pointer events where needed */
#panel-layer .hud,
#panel-layer .room-entry-overlay {
  pointer-events: all;
}
```

- [ ] **Step 3: Replace `frontend/src/main.tsx`**

```typescript
import { StrictMode } from 'react';
import { createRoot }  from 'react-dom/client';
import { AuthProvider } from './contexts/AuthContext';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
```

- [ ] **Step 4: Delete Vite boilerplate files** (generated by scaffold, no longer needed)

```bash
rm -f frontend/src/assets/react.svg frontend/public/vite.svg
```

- [ ] **Step 5: Run all tests**

```bash
npm run test
```

Expected: All tests pass (eventbus: 2, AuthContext: 1, HUD: 6, RoomEntryPrompt: 4 = 13 total).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.css frontend/src/main.tsx
git commit -m "feat: wire up App shell with Phaser game, HUD, and RoomEntryPrompt"
```

---

## Task 18: Integration smoke test

**Files:** None created — this is a manual verification step.

- [ ] **Step 1: Start the FastAPI backend (Terminal 1)**

```bash
cd /path/to/元宝-明翰
uvicorn api.main:app --reload --port 8000
```

Expected: `INFO:     Application startup complete.`

- [ ] **Step 2: Start the frontend dev server (Terminal 2)**

```bash
cd frontend && npm run dev
```

Expected: `  ➜  Local:   http://localhost:3000/`

- [ ] **Step 3: Visitor mode smoke test**

Open `http://localhost:3000` in browser (no `?key=` param).

Verify:
- [ ] Game world renders (dark background, colored room rectangles)
- [ ] HUD shows: `👤 明翰的空间`, room name `🏠 中央活动区`, `💬 和明翰聊天` button
- [ ] No taskboard button, no ⚙ button visible
- [ ] Player (green rectangle) can be moved with WASD/arrow keys
- [ ] Walking toward 健身房 door area shows room entry prompt
- [ ] Prompt shows room name and [Y] / [N] buttons
- [ ] Pressing [N] closes prompt, player movement resumes
- [ ] Pressing [Y] fades to GymScene
- [ ] HUD room name updates to `🏠 健身房`
- [ ] Walking to exit area returns to WorldScene
- [ ] Walking toward 学习室/办公室 doors shows `即将开放` hint (not a room entry prompt)

- [ ] **Step 4: Owner mode smoke test**

Open `http://localhost:3000?key=<your-VITE_PRIVATE_KEY-value>` in browser.

Verify:
- [ ] HUD shows: room name, `📋 任务板` button, `⚙` button
- [ ] No visitor indicator visible
- [ ] Taskboard button shows red badge if there are pending review items
- [ ] Walking near `赛博明翰` NPC and pressing E fires `cyber:npc:interact` event (confirm in browser devtools: `window.addEventListener('cyber:npc:interact', console.log)`)
- [ ] Clicking taskboard button in HUD fires `cyber:object:interact { objectId: 'taskboard' }` (confirm in devtools)

- [ ] **Step 5: TypeScript clean compile**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: Plan 1 complete — React+Phaser game world with HUD and room transitions"
```

---

## Plan 1 complete

At this point:
- React+Vite+TypeScript frontend is running
- All 4 game scenes work (WorldScene, GymScene, OfficeScene/StudyScene stubs)
- Player movement, NPC/object trigger zones, room transitions all functional
- HUD correctly differentiates owner vs visitor
- Room entry prompt handles Y/N confirmation
- EventBus types enforced end-to-end
- 13 unit tests passing

**Next:** Plan 2 will add all functional panels: Dialogue (RPG bar + history expand), Taskboard, Review, KG browser, Prune, and the visitor welcome page.
