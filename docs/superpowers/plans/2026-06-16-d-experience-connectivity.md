# D 体验连接感 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 KG 成长可见、反刍有感知反馈、物品可触发检索、健康对话自动写入 KG。

**Architecture:** SSE 流里新增 `kg_update` 事件类型 → 前端通过 EventBus 驱动 KGPanel 动画和 App 层闪光效果；反刍和物品交互同样走 EventBus 解耦；健康对话每 N 条触发后端 LLM 提取节点直写 KG。

**Tech Stack:** Phaser 3 EventBus (CustomEvent), React useState/useEffect, Vitest + @testing-library/react, FastAPI SSE, Anthropic Python SDK async

---

## File Map

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `api/routes/chat.py` | Modify | 去除 debug 日志；解析 `[KG_UPDATED:]` → 发射 `kg_update` SSE；health 计数 + `_health_to_kg()` |
| `cyber_planner.py` | Modify | `process_message` 在 create/update 工具调用后 yield `[KG_UPDATED:json]` |
| `frontend/src/api/client.ts` | Modify | 去除 debug log；添加 `onKGUpdate?` 参数 |
| `frontend/src/eventbus.ts` | Modify | 添加 3 个新事件类型 |
| `frontend/src/eventbus.test.ts` | Modify | 补充新事件类型测试 |
| `frontend/src/components/panels/DialoguePanel.tsx` | Modify | 接受 `initialQuery` prop；dispatch reflection 和 kg:updated 事件 |
| `frontend/src/components/panels/DialoguePanel.test.tsx` | Modify | 补充 initialQuery 和 reflection dispatch 测试 |
| `frontend/src/components/panels/KGPanel.tsx` | Modify | 监听 `cyber:kg:updated`；refetch；track newNodeIds |
| `frontend/src/components/panels/KGPanel.css` | Modify | 新节点出现动画 |
| `frontend/src/components/panels/KGPanel.test.tsx` | Modify | 测试 refetch + 动画 class |
| `frontend/src/App.tsx` | Modify | 监听 reflection:triggered、object:examine；管理 reflectionFlash |
| `frontend/src/App.css` | Modify | flash overlay CSS |
| `frontend/src/game/objects/TriggerSystem.ts` | Modify | 添加 `examine` zone type |
| `frontend/src/game/scenes/WorldScene.ts` | Modify | 添加书架 examine 触发器 |

---

## Task 1: 清除调试日志

**Files:**
- Modify: `api/routes/chat.py:120-130`
- Modify: `frontend/src/api/client.ts:154`

- [ ] **Step 1: 删除 chat.py 中的 3 条 DEBUG print**

在 `api/routes/chat.py` 中，把以下三行删除：

```python
# 删除这行（约 line 121）:
print(f"[DEBUG] REFLECTION_TRIGGERED received, is_private={is_private}", flush=True)
# 删除这行（约 line 123）:
print(f"[DEBUG] _auto_reflect() returned: {reflection_feature!r}", flush=True)
# 删除这行（约 line 129）:
print(f"[DEBUG] TOOL_LABEL emitted: {label!r}", flush=True)
```

- [ ] **Step 2: 删除 client.ts 中的 debug log**

在 `frontend/src/api/client.ts` line 154，把：

```typescript
if (evt.type === 'tool'  && evt.label)       { console.log('[DEBUG] tool event received:', evt.label); onTool?.(evt.label); }
```

改为：

```typescript
if (evt.type === 'tool'  && evt.label)       onTool?.(evt.label);
```

- [ ] **Step 3: 确认改动正确**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
grep -n "DEBUG" api/routes/chat.py frontend/src/api/client.ts
```

Expected: 无输出（0 matches）

- [ ] **Step 4: Commit**

```bash
git add api/routes/chat.py frontend/src/api/client.ts
git commit -m "chore: remove debug log statements"
```

---

## Task 2: cyber_planner.py — KG 写入时 yield 标记

KG 节点被创建或更新后，`process_message` 向调用方 yield 一条 `[KG_UPDATED:{json}]` 标记，让 SSE 层能把它转成前端事件。

**Files:**
- Modify: `cyber_planner.py:1711-1730`

- [ ] **Step 1: 在 process_message 工具调用后 yield KG_UPDATED 标记**

找到 `process_message` 里处理 tool 结果的循环（大约 line 1711–1730），在 `result = _dispatch_tool(store, block.name, block.input)` 之后插入：

```python
result = _dispatch_tool(store, block.name, block.input)

# 新增：KG 节点写入/更新后 yield 标记，让 SSE 层转成前端事件
if block.name in ("create_memory", "update_memory") and isinstance(result, dict):
    _kg_payload = json.dumps(
        {"id": result.get("uuid", ""), "label": result.get("event_label", "")},
        ensure_ascii=False,
    )
    yield f"[KG_UPDATED:{_kg_payload}]"

tool_results.append({
    ...
})
```

完整修改后的该段代码：

```python
tool_results = []
for block in final_msg.content:
    if block.type != "tool_use":
        continue
    # emit a display label so the frontend can show "正在…"
    _label = _tool_display_label(block.name, block.input)
    yield f"[TOOL_LABEL:{_label}]"
    try:
        result = _dispatch_tool(store, block.name, block.input)
        # KG 节点写入后通知前端
        if block.name in ("create_memory", "update_memory") and isinstance(result, dict):
            _kg_payload = json.dumps(
                {"id": result.get("uuid", ""), "label": result.get("event_label", "")},
                ensure_ascii=False,
            )
            yield f"[KG_UPDATED:{_kg_payload}]"
        tool_results.append({
            "type":        "tool_result",
            "tool_use_id": block.id,
            "content":     json.dumps(result, ensure_ascii=False, default=str),
        })
    except (KeyError, ValueError) as e:
        tool_results.append({
            "type":        "tool_result",
            "tool_use_id": block.id,
            "is_error":    True,
            "content":     str(e),
        })
msgs.append({"role": "user", "content": tool_results})
```

- [ ] **Step 2: 确认语法正确**

```bash
python3 -c "import cyber_planner; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add cyber_planner.py
git commit -m "feat: yield KG_UPDATED marker after create/update_memory tool calls"
```

---

## Task 3: chat.py — 解析 KG_UPDATED；client.ts — 添加 onKGUpdate 回调

**Files:**
- Modify: `api/routes/chat.py` (event_stream 函数)
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: 在 chat.py event_stream 里处理 [KG_UPDATED:] token**

找到 `event_stream()` 中处理 token 的 elif 链（约 line 126–132），在 `elif token.startswith("[TOOL_LABEL:")` 块之后，在 `else:` 块之前添加：

```python
elif token.startswith("[KG_UPDATED:"):
    payload_str = token[12:-1]
    try:
        kg_payload = json.loads(payload_str)
        yield f"data: {json.dumps({'type': 'kg_update', 'nodeId': kg_payload.get('id',''), 'label': kg_payload.get('label','')})}\n\n"
    except (json.JSONDecodeError, KeyError):
        pass
```

完整 event_stream 处理段：

```python
async def event_stream():
    full_text:           list[str] = []
    reflection_triggered: bool     = False
    reflection_feature:   Optional[str] = None

    try:
        async for token in process_message(
                req.message,
                system_prompt_override=resolved_prompt,
                tools_override=resolved_tools,
            ):
            if token == "[REFLECTION_TRIGGERED]":
                reflection_triggered = True
                if is_private:
                    reflection_feature = await _auto_reflect()
                else:
                    reflection_feature = None
            elif token.startswith("[TOOL_LABEL:"):
                label = token[12:-1]
                yield f"data: {json.dumps({'type': 'tool', 'label': label})}\n\n"
            elif token.startswith("[KG_UPDATED:"):
                payload_str = token[12:-1]
                try:
                    kg_payload = json.loads(payload_str)
                    yield f"data: {json.dumps({'type': 'kg_update', 'nodeId': kg_payload.get('id',''), 'label': kg_payload.get('label','')})}\n\n"
                except (json.JSONDecodeError, KeyError):
                    pass
            else:
                full_text.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    except anthropic.APIError:
        pass

    yield f"data: {json.dumps({'type': 'done', 'fullText': ''.join(full_text)})}\n\n"
    yield f"data: {json.dumps({'type': 'reflection', 'triggered': reflection_triggered, 'feature': reflection_feature})}\n\n"
```

- [ ] **Step 2: 在 client.ts 添加 onKGUpdate 回调**

修改 `frontend/src/api/client.ts` 中的 `chatStream` 函数签名和处理：

```typescript
export function chatStream(
  npcId: string,
  message: string,
  privateKey: string,
  onToken: (token: string) => void,
  onDone: (fullText: string) => void,
  onReflection: (triggered: boolean, feature: string | null) => void,
  onTool?: (label: string) => void,
  onKGUpdate?: (nodeId: string, label: string) => void,
): () => void {
```

在 SSE 解析部分，加上：

```typescript
const evt = JSON.parse(line.slice(6)) as {
  type: string;
  content?: string;
  fullText?: string;
  triggered?: boolean;
  label?: string;
  feature?: string | null;
  nodeId?: string;
};
if (evt.type === 'token'     && evt.content)   onToken(evt.content);
if (evt.type === 'done'      && evt.fullText)   onDone(evt.fullText);
if (evt.type === 'reflection')                  onReflection(evt.triggered ?? false, evt.feature ?? null);
if (evt.type === 'tool'      && evt.label)      onTool?.(evt.label);
if (evt.type === 'kg_update' && evt.nodeId)     onKGUpdate?.(evt.nodeId, evt.label ?? '');
```

- [ ] **Step 3: 确认 TypeScript 编译通过**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add api/routes/chat.py frontend/src/api/client.ts
git commit -m "feat: SSE kg_update event for KG write notifications"
```

---

## Task 4: EventBus 新事件 + KGPanel 实时更新 + 节点动画

**Files:**
- Modify: `frontend/src/eventbus.ts`
- Modify: `frontend/src/eventbus.test.ts`
- Modify: `frontend/src/components/panels/KGPanel.tsx`
- Modify: `frontend/src/components/panels/KGPanel.css`
- Modify: `frontend/src/components/panels/KGPanel.test.tsx`

- [ ] **Step 1: 在 eventbus.ts 添加 3 个新事件类型**

把 `CyberEventDetail` 类型修改为：

```typescript
export type CyberEventDetail = {
  'cyber:npc:interact':          { npcId: string; npcName: string };
  'cyber:object:interact':       { objectId: string; contextHint?: string };
  'cyber:object:examine':        { objectId: string; label: string; query: string };
  'cyber:door:approach':         { targetScene: string; roomName: string; modeDescription: string };
  'cyber:scene:changed':         { sceneKey: string; roomName: string };
  'cyber:notification:badge':    { count: number };
  'cyber:panel:opened':          { panelId: string };
  'cyber:panel:closed':          { panelId: string };
  'cyber:door:confirmed':        { targetScene: string };
  'cyber:door:cancelled':        Record<string, never>;
  'cyber:review:done':           { processedCount: number };
  'cyber:kg:updated':            { nodeId: string; label: string };
  'cyber:reflection:triggered':  Record<string, never>;
};
```

- [ ] **Step 2: 确认 TypeScript 编译**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: 无错误（或仅已有错误不增加）

- [ ] **Step 3: 在 KGPanel.test.tsx 写失败测试（refetch on kg:updated）**

在 `frontend/src/components/panels/KGPanel.test.tsx` 中，先添加缺少的 mock：

```typescript
const { mockDispatch, mockListen } = vi.hoisted(() => ({
  mockDispatch: vi.fn(),
  mockListen:   vi.fn(() => vi.fn()), // 返回解绑函数
}));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch, listen: mockListen }));
```

然后在 `describe('KGPanel', ...)` 内添加新测试：

```typescript
it('refetches nodes when cyber:kg:updated event fires', async () => {
  let capturedHandler: ((detail: { nodeId: string; label: string }) => void) | undefined;
  mockListen.mockImplementation((name: string, handler: (d: unknown) => void) => {
    if (name === 'cyber:kg:updated') capturedHandler = handler as typeof capturedHandler;
    return vi.fn();
  });

  render(<KGPanel onBack={vi.fn()} />);
  await waitFor(() => screen.getByText('早起习惯'));
  expect(vi.mocked(getKgNodes)).toHaveBeenCalledTimes(1);

  // 触发 kg:updated 事件
  vi.mocked(getKgNodes).mockResolvedValue([...NODES]);
  await act(async () => { capturedHandler?.({ nodeId: 'n1', label: '早起习惯' }); });

  expect(vi.mocked(getKgNodes)).toHaveBeenCalledTimes(2);
});
```

- [ ] **Step 4: 运行测试，确认失败（FAIL）**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx vitest run src/components/panels/KGPanel.test.tsx 2>&1 | tail -20
```

Expected: `FAIL` — 因为 KGPanel 还没有监听 `cyber:kg:updated`

- [ ] **Step 5: 修改 KGPanel.tsx 实现 refetch + 新节点追踪**

把 `KGPanel.tsx` 顶部 import 行改为：

```typescript
import { useState, useEffect, useCallback } from 'react';
import { dispatch, listen } from '../../eventbus';
import { getKgNodes, type KGNode } from '../../api/client';
import './KGPanel.css';
```

在 `KGPanel` 组件内，把原有的 `useState` 声明替换为：

```typescript
const [nodes,      setNodes]      = useState<KGNode[]>([]);
const [activeTab,  setActiveTab]  = useState<Tab>('all');
const [expandedId, setExpandedId] = useState<string | null>(null);
const [showHelp,   setShowHelp]   = useState(false);
const [loading,    setLoading]    = useState(true);
const [newNodeIds, setNewNodeIds] = useState<Set<string>>(new Set());
```

添加 `fetchNodes` 回调：

```typescript
const fetchNodes = useCallback(() => {
  void getKgNodes(undefined, true).then(data => {
    setNodes(data);
    setLoading(false);
  });
}, []);
```

修改 `useEffect`：

```typescript
useEffect(() => {
  dispatch('cyber:panel:opened', { panelId: 'kg' });
  fetchNodes();

  const offUpdate = listen('cyber:kg:updated', ({ nodeId, label: _label }) => {
    fetchNodes();
    setNewNodeIds(prev => new Set([...prev, nodeId]));
    setTimeout(() => {
      setNewNodeIds(prev => { const s = new Set(prev); s.delete(nodeId); return s; });
    }, 2000);
  });

  return () => {
    dispatch('cyber:panel:closed', { panelId: 'kg' });
    offUpdate();
  };
}, [fetchNodes]);
```

在节点卡片的 `className` 里加上新 class：

```typescript
className={`kg-node-card${node.archived ? ' kg-node-card--archived' : ''}${newNodeIds.has(node.id) ? ' kg-node-card--new' : ''}`}
```

- [ ] **Step 6: 在 KGPanel.css 添加节点出现动画**

在 `KGPanel.css` 末尾添加：

```css
.kg-node-card--new {
  animation: nodeAppear 2s ease-out;
  border-color: #f0a500 !important;
  box-shadow: 0 0 8px rgba(240, 165, 0, 0.4);
}

@keyframes nodeAppear {
  0%   { opacity: 0; transform: scale(0.92); border-color: #f0a500; }
  20%  { opacity: 1; transform: scale(1.02); }
  100% { opacity: 1; transform: scale(1); }
}
```

- [ ] **Step 7: 运行测试，确认通过（PASS）**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx vitest run src/components/panels/KGPanel.test.tsx 2>&1 | tail -20
```

Expected: `PASS` — 所有测试包括新测试通过

- [ ] **Step 8: Commit**

```bash
git add frontend/src/eventbus.ts frontend/src/components/panels/KGPanel.tsx frontend/src/components/panels/KGPanel.css frontend/src/components/panels/KGPanel.test.tsx
git commit -m "feat: KGPanel realtime refetch + node appear animation on kg:updated event"
```

---

## Task 5: 反刍触发金色闪光效果

**Files:**
- Modify: `frontend/src/components/panels/DialoguePanel.tsx`
- Modify: `frontend/src/components/panels/DialoguePanel.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: 在 DialoguePanel.test.tsx 写失败测试**

在 `frontend/src/components/panels/DialoguePanel.test.tsx` 的 mock 声明里确认 `mockListen` 也被 mock（需要新增 listen mock）：

```typescript
const { mockDispatch, mockChatStream } = vi.hoisted(() => ({
  mockDispatch:   vi.fn(),
  mockChatStream: vi.fn(),
}));

vi.mock('../../eventbus', () => ({ dispatch: mockDispatch, listen: vi.fn(() => vi.fn()) }));
vi.mock('../../api/client',  () => ({ chatStream: mockChatStream }));
```

然后添加新测试：

```typescript
it('dispatches cyber:reflection:triggered when reflection fires with triggered=true', async () => {
  let capturedOnReflection: ((triggered: boolean, feature: string | null) => void) | undefined;
  mockChatStream.mockImplementation(
    (_npcId: string, _msg: string, _pk: string,
     _onToken: (t: string) => void, _onDone: (t: string) => void,
     onReflection: (triggered: boolean, feature: string | null) => void) => {
      capturedOnReflection = onReflection;
      return vi.fn();
    },
  );
  wrap();
  fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '测试' } });
  fireEvent.click(screen.getByTestId('dialogue-send'));
  await act(async () => { capturedOnReflection?.(true, null); });
  expect(mockDispatch).toHaveBeenCalledWith('cyber:reflection:triggered', {});
});

it('does NOT dispatch cyber:reflection:triggered when triggered=false', async () => {
  let capturedOnReflection: ((triggered: boolean, feature: string | null) => void) | undefined;
  mockChatStream.mockImplementation(
    (_npcId: string, _msg: string, _pk: string,
     _onToken: (t: string) => void, _onDone: (t: string) => void,
     onReflection: (triggered: boolean, feature: string | null) => void) => {
      capturedOnReflection = onReflection;
      return vi.fn();
    },
  );
  wrap();
  fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '测试' } });
  fireEvent.click(screen.getByTestId('dialogue-send'));
  await act(async () => { capturedOnReflection?.(false, null); });
  expect(mockDispatch).not.toHaveBeenCalledWith('cyber:reflection:triggered', {});
});
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx vitest run src/components/panels/DialoguePanel.test.tsx 2>&1 | tail -20
```

Expected: `FAIL` — cyber:reflection:triggered 测试失败

- [ ] **Step 3: 修改 DialoguePanel.tsx — 在 onReflection 回调里 dispatch 事件**

在 `DialoguePanel.tsx` 的 `sendMessage` 函数里，找到 onReflection 回调：

```typescript
(triggered, feature) => {
  lastReflectionRef.current = triggered;
  if (feature) {
    setMessages(prev => [...prev, {
      id:           Date.now().toString() + '_reflect',
      role:         'npc',
      text:         feature,
      timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
      isReflection: true,
    }]);
  }
},
```

修改为：

```typescript
(triggered, feature) => {
  lastReflectionRef.current = triggered;
  if (triggered) {
    dispatch('cyber:reflection:triggered', {});
  }
  if (feature) {
    setMessages(prev => [...prev, {
      id:           Date.now().toString() + '_reflect',
      role:         'npc',
      text:         feature,
      timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
      isReflection: true,
    }]);
  }
},
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx vitest run src/components/panels/DialoguePanel.test.tsx 2>&1 | tail -20
```

Expected: `PASS`

- [ ] **Step 5: 在 App.tsx 添加闪光状态和监听器**

在 `App.tsx` 中添加 `import { listen } from './eventbus';`（如果还没有）。

在 `App` 组件里添加：

```typescript
const [reflectionFlash, setReflectionFlash] = useState(false);

useEffect(() => {
  const offFlash = listen('cyber:reflection:triggered', () => {
    setReflectionFlash(true);
    setTimeout(() => setReflectionFlash(false), 2000);
  });
  return offFlash;
}, []);
```

在 JSX 里，包裹 `<PhaserGame />` 的容器加上 flash class：

```tsx
return (
  <>
    <div className={`game-wrapper${reflectionFlash ? ' game-wrapper--flash' : ''}`}>
      <PhaserGame />
    </div>
    <div id="panel-layer">
      ...
    </div>
  </>
);
```

- [ ] **Step 6: 在 App.css 添加 flash overlay CSS**

在 `frontend/src/App.css` 末尾添加：

```css
.game-wrapper {
  position: relative;
}

.game-wrapper--flash::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  box-shadow: inset 0 0 80px 30px rgba(240, 165, 0, 0.35);
  animation: reflectionFlash 2s ease-out forwards;
  z-index: 50;
}

@keyframes reflectionFlash {
  0%   { opacity: 1; }
  60%  { opacity: 0.8; }
  100% { opacity: 0; }
}
```

- [ ] **Step 7: 确认 TypeScript 编译**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/panels/DialoguePanel.tsx frontend/src/components/panels/DialoguePanel.test.tsx frontend/src/App.tsx frontend/src/App.css
git commit -m "feat: gold flash overlay on reflection trigger"
```

---

## Task 6: 物品交互 → 自动发送 KG 检索消息

玩家按 E 键检查书架 → DialoguePanel 自动打开并发送预设消息。

**Files:**
- Modify: `frontend/src/game/objects/TriggerSystem.ts`
- Modify: `frontend/src/game/scenes/WorldScene.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/panels/DialoguePanel.tsx`
- Modify: `frontend/src/components/panels/DialoguePanel.test.tsx`

- [ ] **Step 1: 在 DialoguePanel.test.tsx 写失败测试（initialQuery 自动发送）**

在 `frontend/src/components/panels/DialoguePanel.test.tsx` 末尾添加：

```typescript
it('auto-sends initialQuery when provided', async () => {
  mockChatStream.mockReturnValue(vi.fn());

  render(
    <AuthContext.Provider value={{ isOwner: false, privateKey: '' } satisfies AuthContextValue}>
      <DialoguePanel
        npcId="cyber_minghan"
        npcName="赛博明翰"
        onClose={vi.fn()}
        initialQuery="我最近学了什么？"
      />
    </AuthContext.Provider>,
  );

  // 等待 useEffect 运行
  await act(async () => {});
  expect(mockChatStream).toHaveBeenCalledWith(
    'cyber_minghan',
    '我最近学了什么？',
    expect.any(String),
    expect.any(Function),
    expect.any(Function),
    expect.any(Function),
    expect.any(Function),
    expect.any(Function),
  );
});
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx vitest run src/components/panels/DialoguePanel.test.tsx 2>&1 | tail -20
```

Expected: `FAIL` — `initialQuery` prop 不存在

- [ ] **Step 3: 修改 DialoguePanel.tsx 添加 initialQuery prop**

修改 `DialoguePanelProps` 接口：

```typescript
export interface DialoguePanelProps {
  npcId:         string;
  npcName:       string;
  onClose:       () => void;
  initialQuery?: string;
}
```

在组件函数参数中解构：

```typescript
export function DialoguePanel({ npcId, npcName, onClose, initialQuery }: DialoguePanelProps) {
```

在现有 `useEffect` 之后，添加 initialQuery 自动发送逻辑。注意：直接调用 sendText() 而不是通过 input 状态，以避免时序问题：

```typescript
const sendText = useCallback((text: string) => {
  if (!text.trim() || isSending) return;
  setInput('');
  setIsSending(true);
  setStreaming('');
  setToolStatus('思考中…');
  lastReflectionRef.current = false;

  const userMsg: Message = {
    id:           Date.now().toString(),
    role:         'user',
    text:         text.trim(),
    timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
    isReflection: false,
  };
  setMessages(prev => [...prev, userMsg]);

  cancelRef.current = chatStream(
    npcId, text.trim(), privateKey,
    (token)     => { setStreaming(prev => prev + token); },
    (fullText)  => {
      setStreaming('');
      setToolStatus('');
      setIsSending(false);
      setMessages(prev => [...prev, {
        id:           Date.now().toString(),
        role:         'npc',
        text:         fullText,
        timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
        isReflection: lastReflectionRef.current,
      }]);
    },
    (triggered, feature) => {
      lastReflectionRef.current = triggered;
      if (triggered) dispatch('cyber:reflection:triggered', {});
      if (feature) {
        setMessages(prev => [...prev, {
          id:           Date.now().toString() + '_reflect',
          role:         'npc',
          text:         feature,
          timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
          isReflection: true,
        }]);
      }
    },
    (label)     => { setToolStatus(label); },
    (nodeId, label) => { dispatch('cyber:kg:updated', { nodeId, label }); },
  );
}, [npcId, privateKey, isSending]);
```

把原来 `sendMessage` 函数改为调用 `sendText`：

```typescript
const sendMessage = () => {
  const text = input.trim();
  if (!text) return;
  setInput('');
  sendText(text);
};
```

添加 initialQuery 自动发送 useEffect：

```typescript
useEffect(() => {
  if (initialQuery) {
    sendText(initialQuery);
  }
  // 只在 mount 时触发一次，不依赖 sendText 避免无限循环
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, []);
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx vitest run src/components/panels/DialoguePanel.test.tsx 2>&1 | tail -20
```

Expected: `PASS`

- [ ] **Step 5: 修改 TriggerSystem.ts 支持 examine zone 类型**

修改 `TriggerZone` 接口，添加 `examineQuery?`：

```typescript
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
  examineQuery?:    string;
  onTrigger?:       () => void;
}
```

修改 `fireInteract` 方法，添加 examine 处理：

```typescript
private fireInteract(zone: TriggerZone): void {
  if (zone.onTrigger) { zone.onTrigger(); return; }
  if (zone.type === 'npc') {
    dispatch('cyber:npc:interact', { npcId: zone.npcId!, npcName: zone.npcName! });
  } else if (zone.type === 'object') {
    dispatch('cyber:object:interact', { objectId: zone.objectId!, contextHint: zone.contextHint });
  } else if (zone.type === 'examine') {
    dispatch('cyber:object:examine', {
      objectId: zone.objectId ?? zone.id,
      label:    zone.roomName ?? zone.id,
      query:    zone.examineQuery ?? '这里有什么？',
    });
  }
}
```

- [ ] **Step 6: 在 WorldScene.ts 添加书架 examine 触发器**

在 `setupTriggers()` 方法里，在现有 triggers 的末尾添加：

```typescript
.add({ id: 'obj_bookshelf', kind: 'interact', type: 'examine',
       rect: new R(60, 170, 40, 40),
       roomName: '书架',
       examineQuery: '（检查书架）我最近有哪些新发现或学到的东西？' })
```

- [ ] **Step 7: 在 App.tsx 监听 cyber:object:examine**

在 `App.tsx` 的 `useEffect` 里，添加监听：

```typescript
useEffect(() => {
  const offNpc = listen('cyber:npc:interact', ({ npcId, npcName }) => {
    setActivePanel({ id: 'dialogue', npcId, npcName });
  });
  const offObj = listen('cyber:object:interact', ({ objectId }) => {
    if (objectId === 'taskboard' && isOwner) setActivePanel({ id: 'taskboard' });
    if (objectId === 'kg'        && isOwner) setActivePanel({ id: 'kg' });
  });
  const offExamine = listen('cyber:object:examine', ({ query }) => {
    setExamineQuery(query);
    setActivePanel({ id: 'dialogue', npcId: 'cyber_minghan', npcName: '赛博明翰' });
  });
  return () => { offNpc(); offObj(); offExamine(); };
}, [isOwner]);
```

在 `App` 组件顶部，添加 `examineQuery` 状态和对话关闭时清除：

```typescript
const [examineQuery, setExamineQuery] = useState<string | undefined>(undefined);
```

在 DialoguePanel JSX 里，传入 initialQuery，并在 onClose 时清除：

```tsx
{activePanel?.id === 'dialogue' && (
  <DialoguePanel
    npcId={activePanel.npcId}
    npcName={activePanel.npcName}
    onClose={() => { setActivePanel(null); setExamineQuery(undefined); }}
    initialQuery={examineQuery}
  />
)}
```

- [ ] **Step 8: 确认 TypeScript 编译**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/game/objects/TriggerSystem.ts frontend/src/game/scenes/WorldScene.ts frontend/src/App.tsx frontend/src/components/panels/DialoguePanel.tsx frontend/src/components/panels/DialoguePanel.test.tsx
git commit -m "feat: object examine trigger → auto-send KG query to cyber_minghan"
```

---

## Task 7: 健康管家对话 → 自动写入 KG

每 5 条健康对话消息后，提取健康观察并直写 KG，同时通过 SSE 通知前端更新面板。

**Files:**
- Modify: `api/routes/chat.py`
- Modify: `cyber_planner.py` (添加 `health_turns` 到 `_CHAT`)

- [ ] **Step 1: 在 cyber_planner.py 的 _CHAT 添加 health_turns**

找到 `_CHAT: dict = {...}` 声明（约 line 55），添加 `health_turns` 字段：

```python
_CHAT: dict = {
    "client":        None,
    "async_client":  None,
    "store":         None,
    "messages":      [],
    "turns":         0,
    "health_turns":  0,     # 健康管家对话轮次计数
    "system_prompt": "",
}
```

- [ ] **Step 2: 在 chat.py 添加常量和 _health_to_kg 函数**

在 `chat.py` 顶部，在 `from cyber_planner import process_message` 下方，添加：

```python
HEALTH_EXTRACT_EVERY = 5  # 每 5 条健康消息触发一次 KG 提取
```

在 `_auto_reflect` 函数之前，添加 `_health_to_kg` 函数：

```python
async def _health_to_kg() -> Optional[dict]:
    """从最近健康对话中提取健康观察，直接写入 KG Ego 层。
    返回 {"id": uuid, "label": label} 若创建了节点，否则返回 None。"""
    from cyber_planner import _CHAT, MODEL

    state   = _CHAT
    aclient = state.get("async_client")
    store   = state.get("store")
    msgs    = state["messages"]

    if not aclient or not store:
        return None

    # 提取最近 HEALTH_EXTRACT_EVERY * 2 条消息（用户+助手各算一条）
    recent = msgs[-(HEALTH_EXTRACT_EVERY * 2):]
    dialogue_lines = []
    for m in recent:
        if m["role"] == "user" and isinstance(m["content"], str):
            dialogue_lines.append(f"用户: {m['content']}")
        elif m["role"] == "assistant":
            text = (
                " ".join(getattr(b, "text", "") for b in m["content"]).strip()
                if isinstance(m["content"], list)
                else str(m["content"]).strip()
            )
            if text:
                dialogue_lines.append(f"健康管家: {text}")

    if not dialogue_lines:
        return None

    dialogue = "\n".join(dialogue_lines)

    try:
        resp = await aclient.messages.create(
            model=MODEL,
            max_tokens=200,
            system=(
                "你是健康数据提取助手。从对话中提取用户的具体健康行为记录。\n"
                "如果有明确的运动记录、睡眠情况、身体状态或健康目标，"
                "用一句话（不超过60字）描述这个行为事实。\n"
                "如果没有值得记录的具体健康信息，仅输出：NONE\n"
                "只输出描述或 NONE，不要任何解释。"
            ),
            messages=[{"role": "user", "content": f"对话记录：\n{dialogue}"}],
        )
        feature = resp.content[0].text.strip() if resp.content else "NONE"
    except Exception:
        return None

    if not feature or feature.upper() == "NONE":
        return None

    try:
        node = store.create(
            layer="Ego",
            event_label=feature[:40],
            description=feature,
            evidence="[健康管家对话自动提取]",
            batch_id="HealthAuto",
            importance=4,
            source_mode="health_auto",
        )
        return {"id": node.get("uuid", ""), "label": node.get("event_label", "")}
    except Exception:
        return None
```

- [ ] **Step 3: 在 event_stream 中触发 health pipeline**

在 `chat.py` 的 `event_stream()` 函数里，在 `full_text` 等初始化变量之后，添加 health 触发逻辑。把 `event_stream` 函数修改为：

```python
async def event_stream():
    full_text:           list[str] = []
    reflection_triggered: bool     = False
    reflection_feature:   Optional[str] = None
    health_node:          Optional[dict] = None

    try:
        async for token in process_message(
                req.message,
                system_prompt_override=resolved_prompt,
                tools_override=resolved_tools,
            ):
            if token == "[REFLECTION_TRIGGERED]":
                reflection_triggered = True
                if is_private:
                    reflection_feature = await _auto_reflect()
                else:
                    reflection_feature = None
            elif token.startswith("[TOOL_LABEL:"):
                label = token[12:-1]
                yield f"data: {json.dumps({'type': 'tool', 'label': label})}\n\n"
            elif token.startswith("[KG_UPDATED:"):
                payload_str = token[12:-1]
                try:
                    kg_payload = json.loads(payload_str)
                    yield f"data: {json.dumps({'type': 'kg_update', 'nodeId': kg_payload.get('id',''), 'label': kg_payload.get('label','')})}\n\n"
                except (json.JSONDecodeError, KeyError):
                    pass
            else:
                full_text.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    except anthropic.APIError:
        pass

    # 健康管家：每 HEALTH_EXTRACT_EVERY 轮触发 KG 提取
    if req.npcId == "health_coach":
        _state["health_turns"] = _state.get("health_turns", 0) + 1
        if _state["health_turns"] % HEALTH_EXTRACT_EVERY == 0:
            health_node = await _health_to_kg()

    yield f"data: {json.dumps({'type': 'done', 'fullText': ''.join(full_text)})}\n\n"
    yield f"data: {json.dumps({'type': 'reflection', 'triggered': reflection_triggered, 'feature': reflection_feature})}\n\n"

    if health_node:
        yield f"data: {json.dumps({'type': 'kg_update', 'nodeId': health_node['id'], 'label': health_node['label']})}\n\n"
```

- [ ] **Step 4: 确认 Python 语法**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
python3 -c "from api.routes.chat import chat; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: 重启后端，手动验证**

```bash
# 终端 1：后端
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
uvicorn api.main:app --reload --port 8000

# 终端 2：发送 5 条健康消息后查看 KG
# 前端：打开游戏 → 进入健身房 → 跟健康管家聊5条消息
# 观察后端日志：应该没有 [DEBUG] 输出，5条后应出现 kg_update SSE 事件
```

- [ ] **Step 6: Commit**

```bash
git add cyber_planner.py api/routes/chat.py
git commit -m "feat: health coach auto-extracts KG nodes every 5 turns"
```

---

## Task 8: 全量测试 + 最终确认

- [ ] **Step 1: 运行所有前端测试**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx vitest run 2>&1 | tail -30
```

Expected: 所有测试 `PASS`，无新增 `FAIL`

- [ ] **Step 2: 确认 TypeScript 全量编译**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: 无错误

- [ ] **Step 3: 最终 Commit（如有未提交改动）**

```bash
cd /Users/minghan/Desktop/知识蒸馏/元宝-明翰
git status
git add -p  # 逐一确认
git commit -m "chore: finalize D-experience connectivity implementation"
```
