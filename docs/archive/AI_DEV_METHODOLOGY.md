# AI 辅助开发方法论总结

> 从「赛博明翰」Sprint 0 提炼的可复用模式

---

## 这次对话在做什么

用传统软件工程类比，这轮对话是 **Sprint 0（项目启动前置工作）+ 技术负责人工作**。

```
传统 Sprint 0                    本次对话
─────────────────────────────────────────────────────────
写技术设计文档（TDD）        →  TECH_SPEC.md
分配开发任务 + 验收标准      →  AGENT3/4_BRIEF.md
接口契约摘录（按角色）       →  context/ 四个文件
给 AI 写可执行工作单         →  AGENT_PROMPTS.md / WORKBUDDY_PROMPTS.md  ← 新增层
上线前 pre-flight checklist  →  Dry run（模拟执行 + 找 gap）
测试 fixture                 →  gen_placeholders.py + 占位图
```

**多出来的那一层**（可执行工作单 + dry run）是传统流程没有的：人类开发者读完设计文档会自动填补歧义，AI 不会——所以需要专门把这些歧义在执行前找出来并消除。

---

## 可复用的五个模式

### 1. 上下文裁剪

**场景**：现有代码库太大（如 1556 行的 cyber_planner.py），不适合直接扔给 AI。

**做法**：提取一份摘录文件，只保留 AI **需要修改或调用的部分**：
- 公开接口签名
- 关键数据结构字段
- 需要修改的代码行位置
- 不需要理解的内部逻辑：**不写**

```
原文件 1556 行  →  摘录 200 行
保留：CyberBrainStore 接口、handle_review() 的 input() 调用流程、数据字段定义
省略：LLM prompt 构造、KG 内部操作、工具定义
```

**为什么有效**：AI 在大量不相关信息里容易偏离；摘录文件也是跨 session 的稳定"记忆"。

---

### 2. 角色专属上下文文件

**场景**：一个完整 spec（如 TECH_SPEC.md 1161 行）对每个执行角色来说信息太杂。

**做法**：按消费者角色把 spec 拆成小的 context 文件，每个 AI task 只拿自己角色的那份：

```
TECH_SPEC.md（完整规格，1161 行）
    ├── game_context.md      ← Agent 3（Phaser 游戏层）专用
    ├── api_context.md       ← Agent 4 后端专用（API 契约 + I/O 解耦规格）
    ├── panel_context.md     ← Agent 4 前端专用（面板行为 + EventBus + CSS 规范）
    └── cyber_planner_excerpt.md  ← 现有代码摘录
```

**好处**：
- 减少无关噪声，AI 更聚焦
- context 文件比对话历史更稳定，session 重启后仍然有效

---

### 3. Dry Run 验证法

**场景**：写完 prompt 后不确定是否能跑通。

**做法**：在真正执行前，逐步模拟 AI 的第一步行为：

```
第一步：AI 读哪个文件？  →  这个文件存在吗？内容够吗？
第二步：AI 需要写到哪里？  →  目标目录存在吗？
第三步：AI 会调用什么函数？  →  这个函数名在文档里定义了吗？
第四步：AI 需要写 mock 数据？  →  字段名从哪里来？
```

**本次 dry run 发现的问题举例**：

| 问题 | 影响 |
|------|------|
| Task 3 步进前缀写了 `B[N]` 而非 `F[N]` | 工程师命名混乱 |
| CDN 用 `phaser@3`（浮动版本） | 可能引入 breaking change |
| 前端 task 没有附 API schema 文件 | mock 数据字段全靠猜，联调时全改 |
| index.html 不知道需要 `game-container` div | Phaser 初始化失败 |

**经验**：模拟执行前三步就能发现大多数问题，比开始执行后发现便宜得多。

---

### 4. Mock 数据字段来源原则

**场景**：前端先于后端开发，需要写 `USE_MOCK = true` 时的 hardcode 数据。

**错误做法**：只给前端提供函数签名：
```javascript
export async function getReviewItems() {}  // 返回什么？字段叫什么？
```

**正确做法**：同时提供 API 数据结构定义：
```javascript
// ReviewItem 字段（来自 api_context.md）：
// { id, pending_id, proposed_route, proposed_layer,
//   content, raw_evidence, ai_rationale, importance, source_mode }
```

**为什么重要**：mock 数据的字段若与真实 API 不一致，联调时所有面板的数据绑定都要改。

---

### 5. 原子任务纪律

**做法**：AI 每次只实现一个原子任务（一个函数 / 一个文件，≤80 行），等确认后再继续。

所有 AI 开发 prompt 里包含以下规则：
```
每次只实现一个原子任务：
1. 先声明「准备实现：G[N] xxx」
2. 输出代码，控制在 60–80 行以内
3. 说「G[N] 完成，等待确认后继续」
4. 等用户回复「继续」后再进行下一步
```

**为什么有效**：大批量输出后发现问题推倒成本高；小步确认让错误暴露在最小范围，最多只需要推倒一个原子任务。

---

## 完整流程示意

```
1. 写完整技术规格（TECH_SPEC.md）
       ↓
2. 按消费者角色拆分 context 文件
       ↓
3. 为每个 AI agent 写可执行工作单（prompt）
   - 明确项目根目录
   - 明确读哪些文件
   - 明确写到哪里
   - 包含原子任务步进规则
       ↓
4. Dry run（逐步模拟，找 gap）
       ↓
5. 修复 gap，再次验证
       ↓
6. 开始实际执行（开窗口贴 prompt）
```

---

## 哪些是本项目专属的（不可复用）

- 所有具体 prompt 内容（含硬编码路径 `/Users/minghan/Desktop/...`）
- TECH_SPEC.md 和各 BRIEF 文件的具体内容
- assets/ 目录的占位图

---

## 本次对话产出的可直接使用文件

| 文件 | 用途 |
|------|------|
| `docs/AGENT_PROMPTS.md` | 方案 A：Claude Code 启动 prompt（Agent 3 + Agent 4） |
| `docs/WORKBUDDY_PROMPTS.md` | 方案 B：WorkBuddy 三个任务的 prompt |
| `docs/context/game_context.md` | Agent 3 上下文（Phaser 规格） |
| `docs/context/api_context.md` | Agent 4 后端上下文（API 契约） |
| `docs/context/panel_context.md` | Agent 4 前端上下文（面板规格） |
| `docs/context/cyber_planner_excerpt.md` | 现有代码摘录（B1–B5 所需接口） |
| `assets/gen_placeholders.py` | 生成占位图的脚本 |
| `assets/*.png` | 已生成的占位图资产 |

> 下一步：选择方案 A 或 B，打开对应文件，按说明启动 agent 开始写代码。
