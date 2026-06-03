# 赛博明翰 2.0 · 架构重构检查点文档

---

## Phase 1: 数据结构升维

**执行时间**：2026-06-01

**操作文件**：`yuanbao_cyber_minghan_kg.json`

**注入结果**：

| 数组 | 注入节点数 |
|---|---|
| `nodes.Cyber_Minghan.Id_Dynamics` | 38 |
| `nodes.Cyber_Minghan.Superego_Dynamics` | 37 |
| `nodes.Cyber_Minghan.Ego_Dynamics` | 38 |
| `interactions` | 47 |
| **合计** | **160** |

**变更说明**：为每条节点对象新增 `"uuid"` 字段（`uuid4().hex`，32位十六进制字符串），作为后续 Tool Use 动态记忆引擎的精确寻址主键。写入格式：`ensure_ascii=False`，`indent=2`。

**执行脚本**：`migrate_uuid.py`

**状态**：✅ 完成

---

## Phase 2: 基础 CRUD 纯函数库建设

**执行时间**：2026-06-01

**修改文件**：`cyber_planner.py`（新增约 110 行，无大模型 API 调用）

### 架构选型

采用 **单类封装**（`CyberBrainStore`）而非四个散函数，理由：四个操作共享"定位节点"和"安全写盘"两段逻辑，类可避免重复，且后续 Tool Use 注册时一个类即一个数据源，边界清晰。

### 函数签名摘要

| 方法 | 签名 | 说明 |
|---|---|---|
| `retrieve` | `(keyword, limit=10) -> list[dict]` | 跨三层关键词检索，返回精简摘要含 uuid |
| `create` | `(layer, event_label, description, evidence, batch_id="Manual") -> dict` | 追加新节点，自动生成 uuid |
| `update` | `(node_uuid, **fields) -> dict` | 按 UUID 精准更新，返回更新后完整节点 |
| `delete` | `(node_uuid) -> bool` | 按 UUID 精准删除，成功返回 True |

### 遍历策略

三层动力学列表统一由内部方法 `_node_lists()` 聚合为同一迭代入口，所有读写操作对三层结构透明，无需在业务层区分 `Id/Ego/Superego`。

### 安全处理要点

1. **只读字段保护**：`update()` 通过 `_PROTECTED = frozenset({"uuid", "layer"})` 拦截对主键和层级标识的篡改，抛 `ValueError`。
2. **UUID 找不到**：`_find_by_uuid()` 遍历全三层，找不到抛 `KeyError`，`update`/`delete` 均上浮该异常。
3. **layer 合法性校验**：`create()` 通过 `_LAYER_NAME_MAP` 白名单拦截非法层名，防止写入游离节点。
4. **元数据骨架保全**：`_save()` 只更新 `updated_at`，`schema_version`、`metadata`、`processed_batches` 等外层字段均不接触，JSON 覆写前无任何 dict 重建操作。
5. **内存与磁盘一致性**：所有写操作（`create`/`update`/`delete`）均在原地修改 `self._kg` 后立即调用 `_save()`，无中间状态窗口。

### 验证结果

临时脚本 `_test_crud_tmp.py` 运行 5 项断言全部通过后已删除：
- Retrieve：关键词"亲密"命中 4 条，摘要含 uuid ✓
- Create：新节点生成合法 uuid ✓
- Update：正常字段更新 + uuid/layer 只读保护 ✓
- Delete：精准删除 + 重复删除 KeyError ✓
- 元数据完整性：`schema_version`、`metadata`、节点总数均还原 ✓

**状态**：✅ 完成

---

## Phase 3: Tool Schema 协议封装

**执行时间**：2026-06-01

**修改文件**：`cyber_planner.py`（新增全局变量 `CYBER_TOOLS`，约 130 行）

### 工具清单

| Tool Name | 映射函数 | 必填参数 |
|---|---|---|
| `retrieve_memory` | `CyberBrainStore.retrieve` | `keyword` |
| `create_memory` | `CyberBrainStore.create` | `layer`, `event_label`, `description`, `evidence` |
| `update_memory` | `CyberBrainStore.update` | `node_uuid` |
| `delete_memory` | `CyberBrainStore.delete` | `node_uuid` |

### 防呆警告设计

`update_memory` 和 `delete_memory` 在两处埋入了强制前置步骤警告：

1. **工具级 description**（LLM 选择工具时可见）：
   - 明确标注 `⚠️【强制前置步骤 — 违反将导致操作失败】`
   - 明文要求：必须先调用 `retrieve_memory` 获取 uuid，严禁凭猜测填写

2. **参数级 description**（`node_uuid` 字段内）：
   - 二次强调"必须通过 retrieve_memory 工具查询获得，严禁猜测或伪造"
   - `delete_memory` 额外追加："删除操作不可撤销，请在核实 event_label 后再填写"

### 额外设计决策

- `create_memory` 的 `layer` 参数使用 `enum: ["Id", "Superego", "Ego"]`，在 Schema 层直接拦截非法层名，防止 LLM 自由发挥产生游离节点。
- `retrieve_memory` 的 description 中提供了 layer 选择的语义指南，使 LLM 能在 `create_memory` 时做出正确分层判断。
- 所有参数 description 均以中文编写，与 System Prompt 语言风格保持一致，降低 LLM 理解摩擦。

### 验证

Python 静态加载 + 8 项结构断言全部通过（`type`、`properties`、`required` 层级合法；`update`/`delete` 防呆警告覆盖率 100%）。

**状态**：✅ 完成

---

## Phase 4: 上帝指令拦截器

**执行时间**：2026-06-01

**修改文件**：`cyber_planner.py`（新增 `_print_tool_result`、`_dispatch_tool`、`handle_admin_command`，修改 `run()` 两处）

### 路由逻辑

用户在终端输入 `/` 前缀指令时，`run()` 中的路由分支拦截输入，调用 `handle_admin_command(command, client, store)` 并 `continue`，**完全不污染主聊天 `messages` 历史**。

```
用户输入 "/" → handle_admin_command()
               ├─ 构造独立 Admin 上下文（不含聊天历史）
               ├─ Agentic Loop（支持多轮 Tool Use）
               │   ├─ client.messages.create(tools=CYBER_TOOLS)
               │   ├─ stop_reason == "tool_use" → _dispatch_tool() → 打印结果
               │   ├─ 将 tool_result 追回 messages → 再次请求
               │   └─ stop_reason == "end_turn" → 打印最终文本，退出循环
               └─ continue 回主循环
```

### 关键实现决策：Agentic Loop（非单轮）

初版实现为单轮，测试时发现 `delete` 操作需要先 `retrieve` 获取 UUID，属于两轮 Tool Use。  
升级为标准 Agentic Loop：每轮执行完工具后，将 `tool_result` 内容块回传给模型，直到 `stop_reason == "end_turn"` 为止。这是 Anthropic Tool Use 协议的完整闭环实现。

### 容错覆盖

| 场景 | 处理方式 |
|---|---|
| `anthropic.APIError` | 捕获后打印红色错误，`return`，不崩终端 |
| 未知 `tool_name` | `_dispatch_tool` 抛 `ValueError`，作为 `is_error` tool_result 回传 |
| UUID 找不到 | `KeyError` 同上，回传给模型后模型给出自然语言错误提示 |
| `stop_reason` 非预期 | 打印警告并 `break` 退出循环 |
| 模型不调用工具直接 `end_turn` | 打印模型返回的文本并优雅退出 |

### 实机测试结果

通过独立测试脚本（测后已删）对真实 API 进行三轮测试：

| 测试场景 | 指令 | LLM 工具调用链 | 结果 |
|---|---|---|---|
| 检索 | 检索关于孤独感的记忆 | `retrieve_memory(keyword="孤独感")` | 无匹配，模型给出建议词 ✓ |
| 新增 | 新增一条 Ego 层记忆（技术风险规避） | `create_memory(layer="Ego", ...)` | Ego 节点数 38→39，uuid 写入磁盘 ✓ |
| 链式删除 | 找到并删除「技术决策中的风险规避」 | `retrieve_memory` → `delete_memory` | 两轮 Tool Use 自动串联，节点数还原为 38 ✓ |

**状态**：✅ 完成

---

## Phase 5: 主引擎接管 · 动态记忆全局生效

**执行时间**：2026-06-01

**修改文件**：`cyber_planner.py`（替换 `load_cyber_brain` → `build_system_prompt`，重写 `run()` 主循环）

### System Prompt 精简结果

| 指标 | 旧版 | 新版 |
|---|---|---|
| 字数 | ~1,800 字 | **736 字** |
| KG 内容 | 静态注入前 5 条 × 3 层 + 6 条 interactions | **全部移除** |
| 记忆来源 | System Prompt 硬编码 | 运行时 `retrieve_memory` 动态检索 |
| 强制检索令 | 无 | **注入**（询问自身偏好/习惯时必须调用工具） |
| 例外豁免 | 无 | 简单打招呼/确认可直接回复 |

### 主循环 Agentic Loop 实现

主聊天分支的核心结构从"一次性流式调用"升级为**带持久 messages 的 Agentic Loop**：

```
用户消息追加 → while True:
    stream(model, system, tools, messages)
    ├─ stop_reason == "end_turn"  → 打印最终文本，break
    ├─ stop_reason == "tool_use"  → 显示 [查询记忆: xxx]，执行工具
    │   └─ 回传 tool_result → 继续循环（自动流式输出后续文本）
    └─ 其他 stop_reason → 打印警告，break
```

**与 Admin 分支的关键差异**：
- Admin（`handle_admin_command`）：每次指令创建**全新 messages**，无状态
- 主聊天：复用**全局 messages**，保持多轮上下文；工具轮次（assistant+tool_result）自然嵌入序列中

### 上下文协议保证

Anthropic API 要求 `user`/`assistant` 严格交替。工具调用会产生：
```
user(文字) → assistant(tool_use) → user(tool_result) → assistant(文字)
```
这是合法的交替序列。每轮完整记录到 messages 后才进入下一轮，不存在中间态。API 错误时通过 `del messages[turn_start:]` 原子回滚本轮所有追加。

### 实机测试结果

测试问题：**"我最近做项目喜欢用什么技术栈？"**

| 指标 | 结果 |
|---|---|
| Tool Use 触发 | ✓ 是（模型自动检索，未依赖 System Prompt 静态内容） |
| 检索次数 | 6 次（技术栈 / 项目工程 / 编程语言 / 工程洁癖 / 框架 / 开发工具） |
| 最终回复字数 | 219 字 |
| 上下文消息总条数 | 8（含 6 个 tool_result）|
| 消息交替协议验证 | ✓ 无连续同 role 消息 |

**状态**：✅ 完成

---

## Phase 6: 记忆反刍与滚动截断

**执行时间**：2026-06-01

**修改文件**：`cyber_planner.py`（新增 4 个函数、常量 `REFLECT_EVERY=5`、修改 `run()` 末尾触发逻辑）

### 架构组件

| 函数 | 职责 |
|---|---|
| `_extract_dialogue_text(messages)` | 从 messages 列表提取可读对话，过滤 tool_result 条目 |
| `_reflect(client, recent_messages)` | 独立 LLM 请求（max_tokens=200），分析近 N 轮，返回新特征或 NONE |
| `_safe_truncate(messages, keep_turns=2)` | 只在 `user(text)` 边界切割，保留最近 2 个真实轮次 |
| `_reflection_cycle(client, store, messages)` | 完整周期调度：反刍 → 授权 → 写入 → 截断，返回新 messages 列表 |

### 滚动截断安全策略

截断的最大风险是破坏 Anthropic 协议中 `tool_use`/`tool_result` 的配对闭环，或产生连续同 role 消息。

`_safe_truncate` 的解法：**只在 `user(text)` 索引处切割**（非 tool_result 的 user 消息），从倒数第 N 个真实用户发言处保留至结尾。这保证：
1. 截断后首条消息永远是 `user(text)` ✓
2. 不会从 `tool_use`/`tool_result` 对中间切入 ✓
3. 不产生连续同 role 序列 ✓

### Human-in-the-Loop 授权流程

```
反刍引擎输出非 NONE
  → 打印黄色警告：[系统反刍] 提取到新特征：{feature}
  → input("是否写入底层图谱？(Y/N): ")
  → Y → store.create(layer="Ego", batch_id="Reflection", ...)
  → N → 跳过，仅执行截断
```

### 算力保护措施

- 反刍用独立 LLM 请求，`max_tokens=200`（主对话为 2048）
- System Prompt 极简（5 行），无工具挂载，不消耗 Tool Schema Token
- 仅提取文字对话（过滤 tool_result），避免传入冗长 JSON

### 破坏性测试结果

5 轮输入：`实习` → `每天杂活` → `喜欢用脚本` → `能自动化都脚本` → `记住这是我的习惯`

| 指标 | 结果 |
|---|---|
| 反刍触发 | ✓ 第 5 轮结束后自动触发 |
| 特征提取 | ✓「用户习惯用脚本自动化处理重复性杂活，并将其定为默认原则：能自动化的事绝不手动处理」|
| 图谱写入 | ✓ Ego 节点数 38 → 39，batch_id="Reflection" |
| 上下文截断 | ✓ 22 → 8 条消息（保留最近 2 个真实轮次） |
| 截断后首条 | ✓ `user(text)` |
| 消息交替协议 | ✓ 无连续同 role 消息 |

**状态**：✅ 完成

---

## 赛博明翰 2.0 · 架构升级竣工总览

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 1 | UUID 主键注入（160 条节点） | ✅ |
| Phase 2 | CRUD 纯函数库（CyberBrainStore） | ✅ |
| Phase 3 | Anthropic Tool Schema 协议封装（4 工具） | ✅ |
| Phase 4 | 上帝指令拦截器 + Agentic Loop 物理连通 | ✅ |
| Phase 5 | 主引擎接管，System Prompt 精简，动态检索全局生效 | ✅ |
| Phase 6 | 记忆反刍引擎 + Human-in-the-Loop + 滚动截断 | ✅ |
