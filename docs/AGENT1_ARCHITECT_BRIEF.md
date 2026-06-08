# Agent 1：前端架构师 · 任务简报

> 版本：2026-06-07  
> 执行人：用户 + Claude  
> 状态：进行中（TECH_SPEC.md 已完成，各 Agent 任务简报撰写中）

---

## 一、角色定位

**你是什么**：前端项目的规则制定者和信息中枢。你的核心产出是 `TECH_SPEC.md`——一份让三个执行 Agent 能够并行工作、最终产出可以拼合在一起的技术规范文档。

**你负责什么**：
- 做所有架构层的决策（空间方案、技术栈、接口契约、目录结构、事件协议）
- 在执行 Agent 工作期间持续维护 `TECH_SPEC.md`，发现歧义或遗漏立即更新
- 审核各 Agent 交付物是否符合规范，发现偏差给出修正意见

**你不负责什么**：
- 不写任何实现代码（Phaser 场景、FastAPI 路由、HTML 面板）
- 不出任何美术资产（Sprite Sheet、Tilemap、图标）
- 不做产品层面的功能决策（那是用户的事）

**与其他 Agent 的关系**：Agent 1 是所有人的上游。Agent 2、3、4 的工作都 blocked on Agent 1 的规范文档，但 Agent 1 也依赖三个执行 Agent 在实际工作中发现文档的盲点并反馈。

---

## 二、启动前必读

Agent 1 在制定规范前需要掌握的上下文：

**后端代码**（了解现有能力和约束）：
- `cyber_planner.py`：主脑逻辑，REPL 结构，`CyberBrainStore` API
- `pipelines/decision_log.py`：决策池读写，路径硬编码现状
- `health_coach.py`：专项模式模板，`extract_pending()` 逻辑

**现有文档**（了解已对齐的产品决策）：
- `docs/PRODUCT_ALIGNMENT.md`：产品定位、技术栈选型、用户模型
- `docs/UI_DESIGN_DELIVERABLES.md`：视觉参考基准、原始 UI 设计要求
- `docs/SYSTEM_DESIGN_V2.md`：后端架构原则、物理隔离原则

**本项目规范**（Agent 1 自己产出，自己维护）：
- `docs/TECH_SPEC.md`：技术规范文档（六章）
- `docs/FRONTEND_AGENT_PLAN.md`：Agent 拆解方案

---

## 三、依赖与启动条件

**Agent 1 没有外部依赖**——其他所有 Agent 都等 Agent 1，Agent 1 不等任何人。

Agent 1 内部有依赖顺序：

```
① 阅读后端代码和现有文档（已完成）
      ↓
② 解决设计冲突，确定空间方案（已完成：单一住宅 + 多房间）
      ↓
③ 撰写 TECH_SPEC.md 六章（已完成）
      ↓
④ 撰写各 Agent 任务简报（进行中）
      ↓
⑤ 执行 Agent 工作期间持续答疑 + 维护 TECH_SPEC.md（待开始）
```

**Agent 2、3、4 的启动条件**：
- Agent 2 可以启动：TECH_SPEC.md 已完成 ✅ + Agent 2 简报完成后
- Agent 3 可以启动骨架代码：TECH_SPEC.md 已完成 ✅ + Agent 3 简报完成后（资产到位前先用占位图）
- Agent 4 可以启动后端 I/O 解耦：TECH_SPEC.md 已完成 ✅ + Agent 4 简报完成后（不依赖 Agent 2/3）

---

## 四、任务清单

### T1：阅读后端代码与现有文档
**状态**：✅ 已完成  
**验收标准**：能回答「现有后端哪些函数需要 I/O 解耦」「`CyberBrainStore` 是否已参数化」「设计文档之间有哪些矛盾」。

---

### T2：解决设计冲突，确定空间方案
**状态**：✅ 已完成  
**产出**：TECH_SPEC.md 版本范围说明 + 1.2 节（单一住宅 + 多房间，三层映射保留在 /kg 面板内）  
**验收标准**：`PRODUCT_ALIGNMENT.md` 与 `UI_DESIGN_DELIVERABLES.md` 的矛盾已有明确裁定，执行 Agent 不需要再自行判断。

---

### T3：撰写 TECH_SPEC.md（六章）
**状态**：✅ 已完成  
**产出**：`docs/TECH_SPEC.md`，1151 行  
**验收标准**：六章覆盖全部执行 Agent 的启动依赖（已由独立审阅发现 6 处盲点并修复）。

---

### T4：撰写各 Agent 任务简报
**状态**：🔄 进行中（Agent 1 完成，Agent 2/3/4 待写）

| 简报 | 文件 | 状态 |
|------|------|------|
| Agent 1（架构师） | `AGENT1_ARCHITECT_BRIEF.md` | ✅ |
| Agent 2（像素美术 + UI 设计） | `AGENT2_DESIGN_BRIEF.md` | ⏳ |
| Agent 3（Phaser 游戏层） | `AGENT3_GAME_BRIEF.md` | ⏳ |
| Agent 4（面板层 + 接口） | `AGENT4_PANEL_BRIEF.md` | ⏳ |

**验收标准**：每份简报包含五节，执行 Agent 读完后无需提问即可开始工作。

---

### T5：执行期间维护 TECH_SPEC.md
**状态**：⏳ 待开始（执行 Agent 启动后持续进行）  
**触发条件**：任意执行 Agent 发现文档中的歧义、遗漏、或与实际实现不符的内容。  
**处理流程**：

```
执行 Agent 提出问题
  → Agent 1 在 48 小时内给出明确答复
  → 如果答复涉及规范变更，同步更新 TECH_SPEC.md 对应章节
  → 通知所有可能受影响的 Agent
```

**验收标准**：执行期间无执行 Agent 因文档不清晰而自行假设关键决策。

---

### T6：审核各 Agent 交付物
**状态**：⏳ 待开始  
**审核要点**：

| Agent | 审核重点 |
|-------|---------|
| Agent 2 | Sprite Sheet 帧规格（32×48px，行顺序）、文件命名、两状态物件是否齐全 |
| Agent 3 | 场景常量名是否与第二章 2.5 一致、EventBus 事件名是否与第四章精确匹配、是否使用 `roomConfig.js` 数据驱动注册 |
| Agent 4 | API 路由是否与第五章完全对应、I/O 解耦是否彻底（无 `input()`/`print()` 残留）、`sourceMode` 标签展示是否使用映射表 |

**验收标准**：每个 Agent 的交付物通过审核后，Agent 1 在对应 Brief 文件末尾打「✅ 审核通过」标记。

---

## 五、不在范围内

以下是 Agent 1 **明确不做**的事，遇到相关请求应拒绝或转交：

| 不做的事 | 原因 |
|---------|------|
| 写任何实现代码（Phaser 场景、FastAPI 路由、HTML 面板） | 这是 Agent 3 / Agent 4 的职责 |
| 出任何美术资产（Sprite、Tilemap、图标） | 这是 Agent 2 的职责 |
| 调试执行 Agent 代码里的 bug | Agent 1 审核规范符合性，不做技术调试 |
| 决定 Phase 2 / Phase 3 的功能细节 | 当前阶段不需要，决策时机未到 |
| 在文档中预设具体的 UI 交互动效细节 | 动效是 Agent 2 的创意自由区，架构师不越界 |
| 修改现有后端业务逻辑（`cyber_planner.py` 的 KG 操作、反刍逻辑等） | 后端核心逻辑已稳定，不属于前端架构师范围 |

---
