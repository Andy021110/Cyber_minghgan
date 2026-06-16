# Spec 2: D 体验连接感

**目标：** 让三条主线（探索赛博明翰、KG成长可见、健康管家实用）在游戏里产生真实的连接感——玩家能看到知识图谱在变化，能通过游戏世界里的物品触发 KG 查询，健康对话能写入 KG。

**技术栈：** React + Phaser 事件总线、FastAPI SSE、Anthropic API、现有 KG 路由

---

## 1. 架构概述

```
[Phaser 场景] ←─── 事件总线 ───→ [React 面板]
      │                                  │
      │ 物品交互触发                       │ KG 节点动画
      ↓                                  ↓
[游戏事件: examine_object]         [KG 面板: 节点出现动效]
      │
      ↓
[API: POST /chat 携带 context=object_inspect]
      │
      ↓
[赛博明翰: 根据物品检索 KG 并回答]
```

```
[健康管家对话] → [会话结束/定期] → [健康 KG 提取] → [POST /kg/nodes]
```

---

## 2. 功能清单

### 2.1 KG 写入动画

**触发时机：** SSE 流中出现 `type: kg_update` 事件

**效果：**
- KG 面板中对应节点 2s 内从透明淡入，带黄色边框闪烁
- 节点右上角短暂显示 `+1` 数字浮动向上消失

**实现位置：** `frontend/src/components/panels/KGPanel.tsx`

```typescript
// 收到 kg_update SSE 时：
onKGUpdate(nodeId: string) {
  setNewNodes(prev => new Set([...prev, nodeId]));
  setTimeout(() => {
    setNewNodes(prev => { const s = new Set(prev); s.delete(nodeId); return s; });
  }, 2000);
}
```

CSS:
```css
.kg-node.new-node {
  animation: nodeAppear 2s ease-out;
  border: 1px solid #f0a500;
}
@keyframes nodeAppear {
  from { opacity: 0; transform: scale(0.8); }
  to   { opacity: 1; transform: scale(1); }
}
```

---

### 2.2 反刍触发闪光效果

**触发时机：** SSE 流中 `type: reflection` 且 `triggered: true`

**效果：** 游戏画布四边出现 2s 金色光晕（CSS overlay，不影响游戏）

**实现位置：** `frontend/src/components/GameContainer.tsx`（或包裹 canvas 的容器）

```typescript
// 在 DialoguePanel 的 onReflection 回调里同时触发：
if (triggered) {
  setReflectionFlash(true);
  setTimeout(() => setReflectionFlash(false), 2000);
}
```

CSS:
```css
.game-container.reflection-flash::after {
  content: '';
  position: absolute; inset: 0; pointer-events: none;
  box-shadow: inset 0 0 60px 20px rgba(240, 165, 0, 0.4);
  animation: flashFade 2s ease-out forwards;
}
@keyframes flashFade { from { opacity: 1; } to { opacity: 0; } }
```

---

### 2.3 物品交互 → KG 检索

**触发方式：** 玩家走近任务板/书架等物品，按 `F` 键交互

**交互流程：**
1. Phaser 场景发出事件：`EventBus.emit('examine_object', { type: 'task_board', label: '任务板' })`
2. React 层监听到后，在 DialoguePanel 中预填一条消息：`"（查看任务板）我最近有哪些待办？"`
3. 自动发送给赛博明翰（不需要用户手动点发送）
4. 赛博明翰通过 `search_memory` 工具检索 KG 后回答

**新增消息类型：** `role: 'system_action'`（浅灰色气泡，区别于用户输入）

**实现位置：**
- `frontend/src/game/scenes/BaseIndoorScene.ts`：emit 事件
- `frontend/src/components/panels/DialoguePanel.tsx`：监听 EventBus，触发发送

---

### 2.4 健康管家对话 → KG 写入

**触发时机：** 玩家与健康管家每次对话结束（5 条消息后，或用户主动离开）

**提取内容：** 从对话中提取健康类信息节点：
- 运动记录（什么运动、多久、感受）
- 身体状态（睡眠、疲劳感、不适）
- 健康目标（用户提到的打算）

**实现位置：** `api/routes/chat.py` 的 health coach 对话路径（新增 `is_health_coach` 参数）

**提取触发：** 每 `HEALTH_EXTRACT_EVERY=5` 条消息触发一次，调用 `_health_to_kg()`：

```python
async def _health_to_kg(history: list[dict]) -> None:
    """从最近健康对话中提取 KG 节点并写入"""
    # 1. 调用 LLM 提取结构化节点
    # 2. POST /kg/nodes 批量写入
    # 每次提取都带上最近 N 条 health 对话作为上下文
```

---

### 2.5 KG 面板实时更新

**当前问题：** KG 面板数据是页面加载时一次性读取的，写入新节点后不会自动刷新。

**修复方式：** 收到 `type: kg_update` SSE 时，React 调用 `refetchKG()`（现有 KG API hook 里加一个 trigger）。

**实现位置：** `frontend/src/api/client.ts` 的 `onKGUpdate` 回调 + `frontend/src/components/panels/KGPanel.tsx`

---

## 3. 事件总线规范

Phaser ↔ React 通信通过全局 EventBus（`frontend/src/game/EventBus.ts`）：

| 事件名 | 方向 | payload |
|--------|------|---------|
| `examine_object` | Phaser → React | `{ type: string, label: string }` |
| `kg_updated` | React → Phaser | `{ nodeId: string, label: string }` |
| `reflection_triggered` | React → Phaser | `{}` |
| `scene_changed` | Phaser → React | `{ scene: string }` |

---

## 4. API 变更

### 新增 SSE 事件类型

```typescript
// 已有：tool / token / done / reflection
// 新增：
{ type: 'kg_update', nodeId: string, label: string }
```

后端在 `kg.update_node()` 后，把节点 id 和 label 写入 SSE 流。

### 新增端点

无需新端点。健康 KG 提取复用现有 `POST /kg/nodes`。

---

## 5. 不做的事（YAGNI）

- 不做 KG 节点的删除动画（只做新增）
- 不做多房间同时运行（场景切换销毁旧场景）
- 不做健康数据的持久化日志（只写 KG 节点）
- 不做物品交互的 animation（走近高亮就够）
