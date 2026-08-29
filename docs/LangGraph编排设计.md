# LangGraph 编排设计（赛博明翰）

> 日期：2026-08-29 · 状态：设计定稿，已实现于 `agent/`
> 版本：langgraph 1.2.11 / langchain-core 1.6.1

## 1. 为什么要用 LangGraph 重写编排

现有 `cyber_planner.py` 是一个手写的 `while` 循环 Tool Use 闭环（约 1900 行），已经具备 Agent 的形，但有三件事做不好：

| 问题 | 手写循环 | LangGraph |
|---|---|---|
| 状态可回放 | 消息列表在模块级全局 `_CHAT`，无持久化 | checkpointer 按 `thread_id` 落盘，可随时恢复 |
| HITL 中断 | 需要自己实现「暂停-等待-恢复」 | `interrupt()` + `Command(resume=)` 原生支持 |
| 可观测/可测 | 循环内分支靠 print，难断言 | 图结构即状态机，可对节点/边单测 |

依据 Anthropic《Building Effective Agents》的区分：**Workflow 是按预定义代码路径编排 LLM，Agent 是 LLM 动态决定自己的流程**。本项目属于后者（LLM 自主决定调哪个记忆工具），因此需要的是 Agent 框架而不是 DAG 编排器。

## 2. 记忆分层：映射到 LangGraph 的官方定义

LangGraph 官方对两类记忆的定义（原文）：

> **Short-term memory**, or thread-scoped memory, tracks the ongoing conversation by maintaining message history within a session. LangGraph manages short-term memory as a part of your agent's state. State is persisted to a database using a **checkpointer** so the thread can be resumed at any time.

> **Long-term memory** stores user-specific or application-level data across sessions and is shared *across* conversational threads. It can be recalled *at any time* and *in any thread*. Memories are scoped to any custom **namespace**.

官方同时给出三类长期记忆（引自 CoALA 论文的类比）：

| 类型 | 存什么 | 人类例子 | Agent 例子 |
|---|---|---|---|
| Semantic | 事实 | 学校里学的知识 | 关于用户的事实 |
| Episodic | 经历 | 我做过的事 | Agent 过去的动作 |
| Procedural | 规则/指令 | 本能、运动技能 | Agent 的 system prompt |

本项目的映射关系：

| LangGraph 概念 | 本项目实现 | 代码位置 |
|---|---|---|
| 短期记忆（thread-scoped） | `messages` + `working_summary`（滚动摘要，超阈值压缩） | checkpointer（SQLite / InMemory） |
| 长期 · 语义 | L1 动力学 KG（113 节点，Id/Ego/Superego） | `CyberBrainStore` |
| 长期 · 情景 | L0 原文轮次（JSONL append） | `EpisodicStore` |
| 长期 · 程序 | persona / system prompt（反刍可更新） | `persona.md` + Store 预留 |

设计要点：**短期记忆解决"上下文窗口不够"，长期记忆解决"跨会话我不记得"**。两者不能互相替代——把 KG 全塞进 system prompt 是项目早期已废弃的做法（见 `build_system_prompt` 注释）。

## 3. 图结构

```text
START
  │
  ▼
[load_memory]   ← 短期：注入 working_summary；长期：L0/L1 混合检索 → retrieved
  │
  ▼
[agent]         ← LLM 决策（bind tools），产出 AIMessage（可能含 tool_calls）
  │
  ├─(有写类 tool_call)──► [hitl_gate] ──► interrupt() ──► 人工审批 ──► [write_tools]
  │                                                                        │
  ├─(有读类 tool_call)──► [tools]                                          │
  │                          │                                            │
  └──────────────┬───────────┴────────────────────────────────────────────┘
                 ▼
             [agent]  ← 回到 LLM 继续决策（多轮 Tool Use）
                 │
                 ▼ (无 tool_call)
            [persist]  ← 回合结束：append L0、压缩 working_summary
                 │
                 ▼
                END
```

节点职责：

| 节点 | 职责 | 副作用 |
|---|---|---|
| `load_memory` | 拼 system prompt（persona + working_summary + retrieved） | 无（只读） |
| `agent` | 调 LLM，决定说话还是调工具 | 无 |
| `tools` | 只读工具：retrieve_memory / retrieve_episode / list_episodes | 更新 access_count |
| `hitl_gate` | 写类工具审批：create/update/delete_memory | `interrupt()` 暂停 |
| `write_tools` | 审批通过后执行写入 | 写 KG / 写审批队列 |
| `persist` | 落 L0、压缩短期记忆 | 写 JSONL |

**条件边** `route_after_agent`：
- 有 tool_call 且工具名 ∈ 写集合 → `hitl_gate`
- 有 tool_call 且工具名 ∈ 读集合 → `tools`
- 否则（纯文本回复）→ `persist`

## 4. HITL：interrupt 的落点与硬约束

官方要求（原文）：

> To use `interrupt`, you need: 1. A **checkpointer** to persist the graph state 2. A **thread ID** in your config 3. To call `interrupt()` where you want to pause

以及最重要的运行时行为：

> When execution resumes (after you provide the requested input), the runtime restarts the entire node from the beginning—it does not resume from the exact line where `interrupt()` was called. This means any code that ran before the `interrupt` will execute again.

> Because interrupts work by re-running the nodes they were called from, side effects called before `interrupt` should (ideally) be idempotent.

据此定下三条硬约束（写进代码注释）：

1. **`hitl_gate` 内 `interrupt()` 之前不得有任何副作用**（不写 KG、不写日志），只做"构造审批请求 + interrupt"。
2. **禁止用 try/except 包裹 `interrupt()`**：官方明确 "If you wrap the `interrupt` call in a try/except block, you will catch this exception and the interrupt will not be passed back to the graph."
3. **一个节点内只调一次 `interrupt()`**，重问通过 `pending_question` + 条件边循环实现，不用 `while True` + interrupt（会导致指数级重放）。

审批语义沿用既有三档：`approved_kg`（写入 KG）/ `approved_log`（只记日志）/ `rejected`（丢弃），保证与 `pipelines/hitl_review.py` 的既有语义一致。

## 5. 写入纪律：hot path vs background

官方区分两种写入时机：

> Memory can be updated as part of an agent's application logic (e.g., "on the hot path"). In this case, the agent typically decides to remember facts before responding to a user. Alternatively, memory can be updated as a background task.

本项目的选择：

- **L0 情景记忆 → hot path**：回合结束 `persist` 节点自动 append 原文，无需审批（既有设计，原文是事实记录）
- **L1 语义记忆 → hot path + HITL**：Agent 可以在对话中提出写入，但 `hitl_gate` 拦截审批后才落库
- **程序记忆（persona）→ background**：由反刍任务（`_reflect`）异步更新，不阻塞对话

## 6. 与现有代码的关系

- `agent/` 是**新增的平行实现**，不改动 `cyber_planner.py`，CLI 与现有 FastAPI 路由继续可用
- 记忆的 CRUD 复用既有 `CyberBrainStore` / `EpisodicStore`，不重写数据层
- 工具 schema 复用 `CYBER_TOOLS` 的语义（描述文本保持一致），用 LangChain `@tool` 重新声明以便 `ToolNode` 调度

## 7. 测试策略

| 层 | 手段 |
|---|---|
| 状态机 | `FakeChatModel` 脚本化返回 AIMessage（含 tool_calls），断言节点路由 |
| HITL | 断言 `result["__interrupt__"]` 出现，再用 `Command(resume=...)` 恢复并断言写入结果 |
| 记忆 | 临时目录隔离 KG/L0，断言 `working_summary` 压缩与 L0 append |
| 持久化 | `InMemorySaver` 测 thread 隔离；SQLite checker 单独一组 |

## 8. 依据来源

1. LangGraph, *Memory overview* — <https://docs.langchain.com/oss/python/langgraph/memory>
   （短期=thread-scoped+checkpointer；长期=跨线程+namespace；semantic/episodic/procedural 三类；hot path vs background）
2. LangGraph, *Interrupts* — <https://docs.langchain.com/oss/python/langgraph/interrupts>
   （interrupt 三前提；节点从头重执行；禁止 try/except 包裹；禁止 while True + interrupt；`Command(resume=)` 恢复）
3. Anthropic, *Building Effective Agents*（2024-12）— workflow 与 agent 的区分
4. CoALA 论文（Sumers et al., 2023）— 语义/情景/程序记忆映射到 AI Agent
5. 本项目既有实现：`docs/开发方案_企业级对齐.md`、`pipelines/hitl_review.py`（三档审批语义）
