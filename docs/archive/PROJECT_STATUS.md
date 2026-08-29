# 赛博明翰 · 项目状态文档

> 版本：2026-06-03  
> 用途：功能对齐 + UI 开发技术参考  
> 生成方式：逐章补全

---

## 第一章：项目概览

### 1.1 是什么

赛博明翰（Cyber Minghan）是一个以 **精神分析三层结构** 为骨架的个人认知知识库系统。  
它不是普通的笔记工具，而是一个持续追踪「你怎么想、怎么反应、怎么行动」的动态记忆引擎。  
系统通过对话收集原始观察，经过 AI 分类和人工审批，逐渐构建出一张关于「明翰」这个人的认知图谱（KG）。

---

### 1.2 核心概念

**三层心理结构（KG 的组织骨架）**

| 层级 | 键名 | 含义 | 典型节点例子 |
|------|------|------|-------------|
| Id | Id_Dynamics | 本能、欲望、冲动，绕过理性直接行动 | 「任务卡住→立刻去买奶茶」 |
| Ego | Ego_Dynamics | 在现实约束和欲望之间协商的策略 | 「用番茄钟把大任务切成小块」 |
| Superego | Superego_Dynamics | 内化的道德标准、自我批判机制 | 「完成任务后仍觉得不够好」 |

**节点（Node）**  
KG 中最小的存储单元，代表一种可重复出现的行为模式或心理机制。  
每个节点有唯一 UUID，记录该模式的重要程度（importance 1-10）和历史证据。

**Importance 机制**  
- 初始由 AI 根据证据强度建议（通常 4-7）
- 每次新证据指向同一模式时 +1（上限 10）
- 作为 `/prune` 老化时的保护权重：importance 越高越不容易被归档

---

### 1.3 入口与使用方式

```
python3 cyber_planner.py          ← 主入口，认知对话终端
```

启动后进入对话界面，支持以下两种交互：

1. **自然语言对话**：直接和「赛博明翰」聊，系统根据上下文给出回应
2. **命令模式**：输入 `/xxx` 触发功能命令（见第三章）

---

### 1.4 数据存储位置

```
元宝-明翰/
├── cyber_planner.py                 ← 主逻辑
├── health_coach.py                  ← 健康教练模式
├── yuanbao_cyber_minghan_kg.json    ← 知识图谱（核心数据，唯一真相来源）
├── decision_logs/
│   ├── pending.jsonl                ← 待处理观察蓄水池
│   ├── awaiting_approval.jsonl      ← 待人工审批队列
│   └── health_log.jsonl             ← 健康行为日志（不进 KG 的饮食记录等）
└── pipelines/
    ├── batch_processor.py           ← 将 pending 转换为 awaiting_approval
    ├── decision_log.py              ← 队列读写 API
    ├── hitl_review.py               ← 通用 HITL 审查引擎（SOP 规则 / KG 节点审查）
    ├── bio_baseline_final.md        ← 健康教练当前使用的 SOP 协议（58 条宏观防线）
    └── assistant_utils.py           ← 跨模式共享工具（exit 检测等）
```

---

## 第二章：系统架构与数据流

### 2.1 数据生命周期（全链路）

```
用户输入
   │
   ├─ 自然语言对话 ──────────────────────────────────► AI 回应（不写入任何文件）
   │
   └─ /switch（进入健康教练模式）
           │
    health_coach 对话
           │
    [会话结束时] extract_pending()
           │  AI 从对话中提取 0-3 条行为/饮食观察
           ▼
    pending.jsonl  （status="pending"）
           │
    [手动触发] python3 pipelines/batch_processor.py
    [自动触发] 蓄水池 ≥ 20 条时，cyber_planner 启动自动触发
           │  AI 批量分类：路由到 KG 还是 health_log
           ▼
    awaiting_approval.jsonl  （status="awaiting"）
           │
    用户输入 /review
           │  人工逐条审批
           ├─ Y + KG 路由 ──► yuanbao_cyber_minghan_kg.json（写入节点）
           ├─ Y + LOG 路由 ─► health_log.jsonl
           └─ N ───────────► 拒绝，标记 status="rejected"
```

---

### 2.2 主要组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| 认知对话终端 | `cyber_planner.py` | 主入口，对话 + 所有 `/` 命令处理 |
| 健康教练 | `health_coach.py` | 专注健康/饮食对话，会话结束后自动提取观察 |
| 批处理器 | `pipelines/batch_processor.py` | pending → awaiting_approval，AI 分类路由 |
| KG 存储层 | `CyberBrainStore`（cyber_planner.py） | 节点的增删改查，所有写操作必须经过此类 |
| 队列 API | `pipelines/decision_log.py` | pending/awaiting 的读写，状态流转 |
| 老化评分 | `pipelines/prune.py` | staleness 计算，候选归档节点扫描 |
| 相似检测 | `find_similar_nodes()`（cyber_planner.py） | 写入 KG 前检测语义重复 |
| 去重合并 | `scan_duplicate_pairs()`（cyber_planner.py） | 存量节点重复对检测，供 `/prune merge` 使用 |
| HITL 审查引擎 | `pipelines/hitl_review.py` | SOP 规则 / KG 节点 AI 初筛 + 人工裁决，输出干净的宪法 Markdown |

---

### 2.3 KG 节点数据结构

每个节点（Node）是 JSON 对象，存储在 `yuanbao_cyber_minghan_kg.json` 的三个列表中：

```json
{
  "layer":            "Id",
  "event_label":      "任务卡住时→立刻买奶茶逃避",
  "description":      "压力下的即时消费逃避行为",
  "evidence":         "原始证据文本（可追加，多条用换行分隔）",
  "uuid":             "bae4d8f9-...",
  "created_at":       "2026-06-01T10:00:00+00:00",
  "importance":       6,
  "access_count":     3,
  "last_accessed_at": "2026-06-03T08:00:00+00:00",
  "archived":         false,
  "archived_at":      null,
  "archive_reason":   null,
  "source_mode":      "health_coach",
  "batch_id":         "batch_20260601_001"
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_label` | string | 节点标题，格式通常为「触发→行为」 |
| `description` | string | 对该模式的描述，可在 /review 时覆盖 |
| `evidence` | string | 原始证据原文，追加时用换行拼接 |
| `importance` | int 1-10 | 重要度，保护节点不被老化归档 |
| `access_count` | int | 被对话检索的次数 |
| `last_accessed_at` | ISO 8601 | 最近一次被检索的时间 |
| `archived` | bool | 软删除标志，true 表示已归档（数据保留） |
| `archive_reason` | string\|null | 归档原因，`merged_into:uuid[:8]` 表示被合并 |
| `source_mode` | string | 来源（`health_coach` / `legacy` / `test`） |

---

### 2.4 队列数据结构

**pending.jsonl**（每行一条，health_coach 写入）

```json
{
  "id":             "pnd_20260603_001",
  "timestamp":      "2026-06-03T10:00:00+00:00",
  "source_mode":    "health_coach",
  "content":        "AI 提取的观察摘要",
  "raw_evidence":   "原始对话文本",
  "proposed_route": "kg",
  "proposed_layer": "Id",
  "status":         "pending"
}
```

**awaiting_approval.jsonl**（batch_processor 写入）

```json
{
  "id":              "apv_20260603_001",
  "pending_id":      "pnd_20260603_001",
  "content":         "AI 提炼的节点内容",
  "raw_evidence":    "原始证据",
  "proposed_route":  "kg",
  "proposed_layer":  "Id",
  "ai_rationale":    "AI 分类理由",
  "importance":      6,
  "importance_note": "证据中等，模式较典型",
  "status":          "awaiting"
}
```

`status` 状态流转：`awaiting` → `approved_kg` / `approved_log` / `rejected`

---

### 2.5 老化评分公式

```
staleness = days_since_last_access / importance

reference = last_accessed_at（若为 null，取 created_at；两者都 null 则 = 9999）
importance 最小值限为 1（防除零）
```

**阈值**（存储在 KG 的 `meta.prune_config` 中，默认值）：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `staleness_threshold` | 30 | 超过此值进入候选归档 |
| `max_prune_per_session` | 5 | 每次 `/prune` 最多处理条数 |

**示例**：importance=5 的节点，150 天未访问 → staleness = 30，刚好触发阈值

---

### 2.6 AI 调用总览

所有 AI 调用均使用 `claude-sonnet-4-6`，`max_tokens` 根据任务调整：

| 调用场景 | 位置 | 用途 |
|----------|------|------|
| 对话回复 | `cyber_planner.py` 主循环 | 生成赛博明翰的对话回应 |
| 观察提取 | `health_coach.py extract_pending()` | 从对话中提取结构化行为观察 |
| 批量分类 | `batch_processor.py` | 将观察路由到 KG 或 health_log |
| 相似检测 | `find_similar_nodes()` | 新内容写入前检测语义重复 |
| 重复扫描 | `scan_duplicate_pairs()` | 存量节点重复对检测 |
| HITL 规则分类 | `hitl_review.py classify_batch()` | SOP 规则宏观/微观分流（每批 10 条） |
| HITL 改写建议 | `hitl_review.py generate_revision_proposal()` | 根据用户看法生成删除/改写方案 |

---

## 第三章：已实现功能清单

### 3.1 命令总览

| 命令 | 说明 |
|------|------|
| `exit` / `quit` | 退出赛博明翰 |
| `/switch health` | 切换到健康教练模式 |
| `/review` | 打开人工审批队列 |
| `/kg` | 浏览知识图谱（全览） |
| `/kg id` | 只看 Id 层节点 |
| `/kg ego` | 只看 Ego 层节点 |
| `/kg superego` | 只看 Superego 层节点 |
| `/kg archived` | 只看已归档节点 |
| `/prune` | 节点老化检查与归档 |
| `/prune restore` | 恢复已归档节点 |
| `/prune merge` | 扫描并合并语义重复节点 |
| `/任意自然语言指令` | 管理员指令（Tool Use 模式，直接操作 KG） |
| 直接输入文字 | 正常对话（赛博明翰会结合 KG 回应） |

---

### 3.2 自然语言对话

**触发方式**：直接输入任何不以 `/` 开头的文字

**行为**：
- 系统用 `build_system_prompt()` 把 KG 的高重要度节点注入到 system prompt
- AI 基于明翰的认知图谱做有记忆的回复
- 每轮对话后，AI 可能调用 Tool Use 自动检索/更新节点（`retrieve_memory`）
- 被检索到的节点 `access_count +1`，`last_accessed_at` 更新

**UI 关注点**：需要区分「AI 文本流」和「Tool Use 执行日志」两类输出

---

### 3.3 /switch health — 健康教练模式

**触发**：`/switch health`

**流程**：
1. 从当前对话提取摘要（trigger_context），作为进入健康教练时的上下文
2. 提示确认切换（Y/N）
3. 启动 `health_coach.run(trigger_context=...)`
4. 健康教练对话结束后，AI 自动提取 0-3 条观察写入 `pending.jsonl`
5. 返回赛博明翰主界面（原对话历史不继承）

**健康教练特点**：
- 只读 KG（不写入），专注健康/饮食/行为话题
- 会话结束的触发：用户输入 `exit`/`quit`/`退出` → 确认 Y/N

**UI 关注点**：两种模式有不同的角色定位，UI 可用标签页或状态栏区分当前模式

---

### 3.4 /review — 人工审批队列

**触发**：`/review`（也可在启动时看到待审提醒后直接输入）

**两步交互流程**：

**第一步（决策）**：
```
[N/Total] 路由: KG → Id 层
  观察内容: XXX
  原始证据: XXX
  AI 分类:  XXX
  Y=采纳  N=拒绝  s=跳过本条  q=暂停审批
```

| 输入 | 行为 |
|------|------|
| `Y` | 采纳，进入第二步（KG 路由）或直接写入（LOG 路由） |
| `N` | 拒绝，可选输入理由，条目标记 rejected |
| `s` | 跳过本条，保留 awaiting 状态，下次 /review 再审 |
| `q` | 暂停，显示剩余条目数，退出审批模式 |

**第二步（仅 KG 路由触发）**：
1. 相似节点检测（`find_similar_nodes`）：若找到语义相似节点，列出并询问
   - 输入 `1~N`：追加证据到已有节点（importance +1），不创建新节点
   - 输入 `i`：忽略相似，新建节点
   - 输入 `n`：新建节点（等同于 `i`）
2. 确认 importance（回车接受 AI 建议 / 输入数字覆盖）
3. 确认 description（回车保留原文 / 输入新文本替换）

**UI 关注点**：这是系统数据入口，UI 需要支持键盘快捷键（Y/N/s/q），并显示相似节点卡片

---

### 3.5 /kg — 知识图谱浏览

**触发**：`/kg` 及子命令

**输出格式**：
```
═══════════════════════════════
  Cyber Minghan 知识图谱
  活跃 130 条 · 归档 3 条
═══════════════════════════════

Id — 本能欲望  (45 条)
  [6] 任务卡住时→立刻买奶茶逃避
  [5] 截止日期前的习惯性逃避...
  ...

Ego — 现实协商  (47 条)
  ...

Superego — 道德规范  (38 条)
  ...

已归档  (3 条)
  [3] [已归档] 某某节点  archived_reason: staleness
  ...
```

每个节点显示 `[importance] event_label`，归档节点额外显示归档原因。

**子命令**：

| 命令 | 效果 |
|------|------|
| `/kg` | 全览：三层 + 底部归档区 |
| `/kg id` | 只显示 Id 层 |
| `/kg ego` | 只显示 Ego 层 |
| `/kg superego` | 只显示 Superego 层 |
| `/kg archived` | 只显示归档节点 |

**UI 关注点**：天然适合卡片式 / 分组列表展示，importance 可做颜色或大小映射

---

### 3.6 /prune — 节点老化管理

**触发**：`/prune`

**流程**：
1. 计算所有节点的 staleness 分数
2. 显示分布概览：候选归档 / 接近阈值 / 健康 / 已归档
3. 按 staleness 降序取前 N 条（默认 5 条）逐条裁决

**每条节点的操作选项**：

| 输入 | 行为 |
|------|------|
| `a` | 归档该节点（软删除，archived=true） |
| `b` | 提升 importance +1（保护节点） |
| `s` | 跳过 |

---

### 3.7 /prune restore — 恢复归档节点

**触发**：`/prune restore`

列出所有已归档节点，用户输入编号恢复（archived=false，archive_reason 清空）。

---

### 3.8 /prune merge — 语义重复合并

**触发**：`/prune merge`

**流程**：
1. 调用 `scan_duplicate_pairs()`：AI 扫描所有活跃节点，返回语义重叠的节点对
2. 逐对展示，用户裁决

**每对节点的操作选项**：

| 输入 | 行为 |
|------|------|
| `1` | 保留 A，归档 B（B 的证据合并到 A） |
| `2` | 保留 B，归档 A（A 的证据合并到 B） |
| `s` | 跳过，两条节点不变 |
| `q` | 结束 merge，显示统计 |

**合并规则**：
- winner.importance = min(max(a.importance, b.importance) + 1, 10)
- winner.evidence 追加 loser 的 evidence（换行拼接）
- loser.archived = true，archive_reason = `merged_into:{winner_uuid[:8]}`

---

### 3.9 管理员指令（Tool Use 模式）

**触发**：任何以 `/` 开头但不匹配以上命令的输入

**示例**：
```
/把「压力逃避」节点的重要度改为 8
/删除 uuid=xxx 的节点
/查找所有 Ego 层的节点
```

AI 在管理员模式下可使用四个工具：

| 工具 | 说明 |
|------|------|
| `retrieve_memory` | 按语义检索节点 |
| `create_memory` | 创建新节点 |
| `update_memory` | 更新节点字段 |
| `delete_memory` | 删除节点（物理删除） |

**UI 关注点**：这是一个自由文本指令入口，UI 可以设计为「指令模式」的特殊输入框

---

## 第四章：测试状态

### 4.1 自动化测试（全部通过）

截至 2026-06-03，共 8 个测试文件，全部通过。

| 测试文件 | 覆盖功能 | 通过状态 |
|----------|----------|----------|
| `test_phase7_8.py` | KG 老化评分、staleness 归档、/prune 触发逻辑、health_log 超龄清理 | ✓ |
| `test_extract_pending.py` | health_coach 提取逻辑（饮食记录、行为模式、纯问答不提取） | ✓ |
| `test_exit_command.py` | `is_exit_command()` 识别、`confirm_exit()` Y/N 确认 | ✓ |
| `test_review_ui.py` | /review 两步决策流（A1）、s/q 语义统一（A2）、无效输入重提示 | ✓ |
| `test_kg_browse.py` | /kg 全览、层级过滤、归档区位置、importance 标记格式（B1+B2） | ✓ |
| `test_similar_nodes.py` | 相似内容能找到已有节点、无关内容返回空、top_k 限制（C1） | ✓ |
| `test_review_dedup.py` | 追加证据路径（importance+1、不新建节点）、新建路径、client=None 跳过、i=忽略（C2） | ✓ |
| `test_prune_merge.py` | scan_duplicate_pairs 检测、选1保留A/选2保留B、s跳过、archive_reason 格式（D1） | ✓ |

运行全部测试：
```bash
for f in test_phase7_8 test_extract_pending test_exit_command test_review_ui \
          test_kg_browse test_similar_nodes test_review_dedup test_prune_merge; do
  python3 pipelines/$f.py
done
```

---

### 4.2 手动测试状态

#### 已完成

| 场景 | 验证内容 | 结论 |
|------|----------|------|
| T4 端到端管道 | health_coach → pending → batch_processor → /review 全链路 | ✓ 通过 |
| /review LOG 路由 | 饮食记录正确路由到 health_log，不进 KG | ✓ 通过 |
| /review KG 路由（两步流程） | Y → 相似检测触发 → importance 确认 → description 确认 → 写入 | ✓ 通过 |
| 相似节点 UI 展示 | 进入 KG 路由时正确列出 3 个相似节点，格式可读 | ✓ 通过 |
| 选 `i` 忽略相似，新建节点 | 新节点正常写入 KG | ✓ 通过 |

#### 未完成（待手动验证）

| 场景 | 验证内容 | 优先级 |
|------|----------|--------|
| /review 追加证据到已有节点（选 1~N） | importance +1，evidence 追加，无新建节点 | **高** |
| /review 手动覆盖 importance | 输入数字后节点 importance 以覆盖值写入 | 中 |
| /review 手动覆盖 description | 输入新文本后节点描述以新值写入 | 中 |
| /review `s` 跳过 | 跳过后条目保留，下次 /review 可再审 | 中 |
| /review `q` 暂停 | 暂停后剩余条目保留，显示「剩余 N 条」 | 中 |
| /prune merge 交互 UI | 查看真实终端中 merge UI 的样式，选 1/2/s/q | **高** |
| /prune merge 选 1 合并 | winner importance 提升，loser 出现在 /kg archived | **高** |
| /kg 视觉格式 | 三层标题、importance 标记、归档区位置的视觉效果 | 低 |
| health_coach exit 确认流程 | exit → 确认 Y → 返回赛博明翰，观察提取日志 | 低 |

---

### 4.3 推荐手动测试顺序

按依赖关系排序，前面的测试可以为后面的提供数据：

**Step 1**：生成测试数据
```
python3 cyber_planner.py
> /switch health
（在健康教练里说一些有触发模式的事）
（exit → Y）
python3 pipelines/batch_processor.py
```

**Step 2**：测试 /review 完整交互
```
> /review
```
- 对 LOG 路由条目：输入 `Y`，验证直接写入
- 对 KG 路由条目：输入 `Y` → 如有相似节点选 `1`（追加证据）→ 验证 importance+1
- 再进一条类似的：输入 `Y` → 手动改 importance 为 `8` → 手动改 description

**Step 3**：测试 /review 的 s/q
```
> /review
```
- 第一条：输入 `s`，验证保留
- 再次 `/review`，出现刚才跳过的条目
- 输入 `q`，验证显示剩余条数

**Step 4**：测试 /prune merge
```
> /prune merge
```
- 观察 UI 格式
- 对第一个重复对：输入 `1`
- 之后 `/kg archived` 验证 loser 出现在归档列表

**Step 5**：验证 /kg 视觉
```
> /kg
> /kg id
> /kg archived
```

---

## 第五章：UI 开发技术参考

### 5.1 核心设计原则

当前系统 100% 基于 `input()` / `print()` 的 CLI 交互。UI 层的职责是**替换这两层 I/O**，后端逻辑不需要改动。

三个关键约束：
1. **KG 只有一个写入路径**：所有写操作必须经过 `CyberBrainStore`，不能直接操作 JSON 文件
2. **AI 调用全部阻塞**：当前没有异步化，每次 AI 调用会卡住主线程直到返回（对话回复除外，支持 streaming）
3. **状态存储全在文件**：KG、队列、通知都是 `.jsonl` / `.json` 文件，无数据库，UI 轮询文件即可感知状态变化

---

### 5.2 可直接复用的后端 API

UI 层应该调用这些函数，而不是重新实现逻辑：

**KG 读写（`CyberBrainStore`，位于 `cyber_planner.py`）**

```python
store = CyberBrainStore()                          # 加载 KG
store.retrieve(keyword, limit=10)                  # 语义检索节点，返回 list[dict]
store.create(layer, event_label, description,      # 创建节点，返回新节点 dict
             evidence, importance, source_mode)
store.update(uuid, **fields)                       # 更新节点字段，返回更新后 dict
store.delete(uuid)                                 # 物理删除节点，返回 bool
```

> 注意：`CyberBrainStore` 每次实例化都从文件重新加载。如果 UI 需要持续展示最新状态，需要在操作后重建实例或手动重载 `store._kg`。

**队列读写（`pipelines/decision_log.py`）**

```python
from pipelines.decision_log import (
    read_awaiting,          # 返回所有 status="awaiting" 的条目 list[dict]
    resolve_approval,       # 标记条目为 approved_kg / approved_log / rejected
    count_pending,          # 返回 pending 数量
    read_unconsumed_notifications,  # 未消费的系统通知
    consume_notification,   # 标记通知为已消费
)
```

**节点相似检测（`cyber_planner.py`）**

```python
from cyber_planner import find_similar_nodes
results = find_similar_nodes(new_content, store, client, top_k=3)
# 返回 list[dict]，每条附加 _similarity_reason 字段
```

**重复对扫描（`cyber_planner.py`）**

```python
from cyber_planner import scan_duplicate_pairs
pairs = scan_duplicate_pairs(store, client)
# 返回 [{"node_a": {...}, "node_b": {...}, "reason": "..."}, ...]
```

**节点归档（`cyber_planner.py`）**

```python
from cyber_planner import _archive_node
_archive_node(store, node_uuid)
```

---

### 5.3 数据读取接口（UI 展示层）

**获取所有活跃节点（按层）**：

```python
store = CyberBrainStore()
kg = store._kg["nodes"]["Cyber_Minghan"]

id_nodes       = [n for n in kg["Id_Dynamics"]       if not n.get("archived")]
ego_nodes      = [n for n in kg["Ego_Dynamics"]       if not n.get("archived")]
superego_nodes = [n for n in kg["Superego_Dynamics"]  if not n.get("archived")]
archived_nodes = [n for n in kg["Id_Dynamics"] + kg["Ego_Dynamics"] + kg["Superego_Dynamics"]
                  if n.get("archived")]
```

**节点卡片所需字段**（UI 展示最小集）：

| 字段 | 用途 |
|------|------|
| `uuid` | 唯一标识，操作时传参 |
| `layer` | 显示所属层（Id / Ego / Superego） |
| `event_label` | 节点标题（主要显示文本） |
| `description` | 详细描述（展开后显示） |
| `evidence` | 原始证据（折叠/弹窗显示） |
| `importance` | 1-10，可做颜色/大小映射 |
| `access_count` | 被检索次数，可做热度指示 |
| `last_accessed_at` | 最后访问时间 |
| `archived` | 是否归档 |
| `archive_reason` | 归档原因（`merged_into:uuid` 或老化说明） |

**获取待审批队列**：

```python
from pipelines.decision_log import read_awaiting
items = read_awaiting()
# 每条含: id, content, raw_evidence, proposed_route, proposed_layer,
#         ai_rationale, importance, importance_note
```

---

### 5.4 AI 对话接入方式

当前对话是同步 streaming，UI 接入有两种选择：

**方案 A：保持 CLI 进程，UI 作为前端壳**
- UI 起一个子进程运行 `cyber_planner.py`
- 捕获 stdout（流式文本块）→ 实时显示
- 向 stdin 写入用户输入
- 适合快速原型，但解析 ANSI 颜色码麻烦

**方案 B：直接调用 Anthropic SDK（推荐）**
- UI 自己维护 `messages` 列表和 `store` 实例
- 直接调用 `client.messages.stream(...)` 获取 streaming 响应
- 工具回调（Tool Use）需要自行实现 `_dispatch_tool` 的等价逻辑
- 更干净，但需要把 `cyber_planner.py` 的对话逻辑提取出来

**Streaming 响应示例**（方案 B 参考）：

```python
with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    system=system_prompt,
    tools=CYBER_TOOLS,
    messages=messages,
) as stream:
    for chunk in stream.text_stream:
        ui.append_text(chunk)   # 实时追加到 UI 文本区
    final = stream.get_final_message()
```

---

### 5.5 反刍引擎（需要 UI 支持的特殊交互）

每 5 轮对话触发一次「反刍」：AI 分析最近对话，提取可能的新行为特征，询问是否写入 KG。

触发条件：`turns % 5 == 0`（turns 为真实用户轮次计数）

UI 需要处理的中断：
```
[反刍引擎] 正在分析最近 5 轮对话...
[系统反刍] 提取到新特征：XXX
是否写入底层图谱？(Y/N):
```

这是一个阻塞式人工授权步骤，UI 需要弹出确认对话框，不能静默处理。

---

### 5.6 batch_processor 触发时机

| 触发方式 | 条件 | 建议 UI 处理 |
|----------|------|-------------|
| 自动触发 | pending ≥ 20 条，cyber_planner 启动时检测 | 显示进度条/loading 状态 |
| 手动触发 | `python3 pipelines/batch_processor.py` | UI 提供「处理蓄水池」按钮 |

batch_processor 调用方式（从 Python 调用）：

```python
import sys
sys.path.insert(0, "pipelines")
import batch_processor as bp
written = bp.run(dry_run=False)   # 返回写入 awaiting_approval 的条目数
```

---

### 5.7 状态轮询建议

UI 需要感知的状态变化（无 websocket，靠文件轮询）：

| 状态 | 检测方法 | 建议轮询频率 |
|------|----------|-------------|
| 待审批数量变化 | `count_pending("awaiting")` → 对应 `read_awaiting()` | 每 5 秒 |
| 蓄水池新增 | `count_pending("pending")` | 每 10 秒 |
| KG 节点变化 | 比较 `kg.updated_at` 字段 | 操作后即时刷新 |
| 系统通知 | `read_unconsumed_notifications()` | 每 5 秒 |

---

### 5.8 配置参数（可在 UI 设置面板暴露）

全部存储在 `yuanbao_cyber_minghan_kg.json` 的 `meta.prune_config`：

| 参数 | 当前值 | 含义 |
|------|--------|------|
| `staleness_threshold` | 30 | 老化归档阈值（days/importance） |
| `prune_interval_days` | 90 | 多少天没跑 /prune 就提醒 |
| `health_log_retention_days` | 90 | health_log 保留天数 |
| `max_prune_per_session` | 5 | 每次 /prune 最多处理条数 |

修改方式：

```python
store = CyberBrainStore()
store._kg.setdefault("meta", {}).setdefault("prune_config", {})["staleness_threshold"] = 20
store._save()
```

---

## 第六章：UI 开发前的开放问题与设计建议

### 6.1 需要先决策的问题

在动手写 UI 之前，以下几个问题会直接影响技术选型，建议先对齐：

**Q1：UI 形态是什么？**

| 选项 | 优点 | 缺点 |
|------|------|------|
| Web 应用（本地起服务）| 技术栈熟悉，跨平台，易于布局 | 需要一个 Python backend server |
| 桌面应用（Electron/Tauri）| 原生文件访问，无需 server | 打包复杂 |
| Streamlit / Gradio | 极快原型，几乎不用写前端 | 布局自由度低，实时 streaming 支持有限 |

**推荐**：如果只是个人工具，Streamlit 最快落地；如果要做成产品级，Web 应用（FastAPI + React/Vue）最灵活。

---

**Q2：AI 对话如何接入 UI？**

当前 `cyber_planner.py` 的对话逻辑与 `input()`/`print()` 深度耦合。UI 接入有两条路：

- **路径 A（快）**：把 `handle_review`、`handle_kg`、`handle_prune` 这些纯逻辑函数改造成返回数据而非 print，只改 I/O 层，不动核心逻辑
- **路径 B（干净）**：把 `cyber_planner.py` 拆成 `brain_core.py`（纯逻辑，返回数据）+ `cli.py`（CLI 的 print/input 层），UI 直接用 `brain_core`

**推荐路径 A 先行**，等功能稳定后再做路径 B 的重构。

---

**Q3：batch_processor 怎么触发？**

CLI 里是「启动时检测 pending ≥ 20 自动触发」。UI 里需要决定：
- 后台定时任务（每 X 分钟检查一次）
- 用户手动点「处理待观察」按钮
- health_coach 对话结束后立即触发（不等积累到 20 条）

**推荐**：UI 里去掉 20 条的阈值限制，每次 health_coach 对话结束后立即自动处理。

---

**Q4：文件并发写入怎么处理？**

当前系统是单进程 CLI，不存在并发问题。但 UI 可能同时有：后台轮询线程 + 前台操作 + batch_processor 并发写同一个 `.jsonl` 文件。

`decision_log.py` 目前没有文件锁。轻量解决方案：写入前加 `fcntl.flock`（Unix）或改为 SQLite（更健壮）。

**短期**：UI 写操作串行化（用队列），暂时不需要文件锁。

---

### 6.2 三个核心界面的布局建议

#### 界面 1：对话主界面

```
┌─────────────────────────────────────────────┐
│  赛博明翰  ·  [对话模式]      [通知 2] [⚙]  │
├──────────────┬──────────────────────────────┤
│              │                              │
│  知识图谱    │      对话区域                │
│  侧边栏      │                              │
│              │  赛博明翰: ...               │
│  Id (45)     │  你: ...                     │
│  ├ [6] 节点  │  赛博明翰: ...（streaming）  │
│  ├ [5] 节点  │                              │
│  ...         ├──────────────────────────────┤
│  Ego (47)    │  [输入框]              [发送] │
│  Superego    └──────────────────────────────┘
│  (38)        
│  ── 归档 3   
└──────────────
```

**关键 UX 细节**：
- 侧边栏节点按 importance 排序，高 importance 节点排前面
- 对话中 AI 触发 Tool Use（检索/更新节点）时，侧边栏对应节点高亮闪烁
- 反刍引擎触发时，对话区出现「写入图谱？」的行内确认卡片，而非弹窗

---

#### 界面 2：/review 审批界面

```
┌─────────────────────────────────────────────┐
│  待审批  ·  共 3 条                          │
├─────────────────────────────────────────────┤
│  [1/3]  KG → Id 层                          │
│  ┌───────────────────────────────────────┐  │
│  │ 任务卡住时去刷手机逃避压力             │  │
│  │ 原始: 最近项目压力大，任务卡住就...   │  │
│  │ AI: 压力触发逃避冲动，稳定因果模式    │  │
│  └───────────────────────────────────────┘  │
│                                              │
│  ⚠ 相似节点                                 │
│  ┌───────────────────────────────────────┐  │
│  │ [1] 截止日期前的习惯性逃避  [Ego, 5]  │  │
│  │     相似：压力下刷手机逃避，高度重合  │  │
│  └───────────────────────────────────────┘  │
│                                              │
│  importance: [6] ←→     description: [编辑] │
│                                              │
│  [追加到节点1]  [新建]  [跳过]  [拒绝]      │
└─────────────────────────────────────────────┘
```

**关键 UX 细节**：
- 相似节点可以展开查看完整证据，帮助判断是否真的重复
- importance 用滑块而非输入框，更直观
- 「追加到节点 N」按钮自动对应检测到的相似节点编号

---

#### 界面 3：/kg 知识图谱界面

```
┌─────────────────────────────────────────────┐
│  知识图谱  ·  活跃 130  归档 3     [搜索]    │
│  [全部] [Id] [Ego] [Superego] [已归档]       │
├──────────────┬──────────────┬────────────────┤
│  Id — 本能   │  Ego — 现实  │ Superego — 道德│
│  欲望 (45)   │  协商 (47)   │ 规范 (38)      │
│              │              │                │
│  ┌─────────┐ │  ┌─────────┐ │  ┌───────────┐ │
│  │[6] 任务 │ │  │[7] 番茄 │ │  │[6] 完成后 │ │
│  │卡住→买  │ │  │钟切分   │ │  │过度自责   │ │
│  │奶茶     │ │  │大任务   │ │  │           │ │
│  └─────────┘ │  └─────────┘ │  └───────────┘ │
│  ...         │  ...         │  ...           │
└──────────────┴──────────────┴────────────────┘
```

也可以切换到已有的**力导向图视图**（`generate_viz.py` 输出的 HTML，使用 vis-network 库）：
- Id 层：红色节点 `#e05c5c`
- Ego 层：绿色节点 `#3fb950`
- Superego 层：橙色节点 `#f0a500`

---

### 6.3 现有可复用资产

| 资产 | 位置 | 说明 |
|------|------|------|
| 力导向图 HTML | `docs/cyber_minghan_graph.html` | 已可运行的 vis-network 图谱可视化 |
| 图谱生成脚本 | `pipelines/generate_viz.py` | 从 KG JSON 生成 HTML，可改为返回数据供 UI 渲染 |
| 色彩方案 | 见上 | Id=红、Ego=绿、Superego=橙，暗色背景 `#0d1117` |

---

### 6.4 不需要 UI 改动的功能

以下功能在当前 CLI 里工作正常，UI 里可以直接调用对应函数，不需要额外设计：

- `CyberBrainStore.retrieve()` — 语义检索（对话时 AI 自动调用）
- `scan_duplicate_pairs()` — /prune merge 的后端逻辑
- `find_similar_nodes()` — /review 写入前的去重检测
- `pipelines/prune.py` — 老化评分计算

---

### 6.5 需要改动才能适配 UI 的部分

| 当前实现 | 问题 | 建议改法 |
|----------|------|----------|
| `handle_review()` 直接 print + input | UI 无法接管 I/O | 改为返回条目列表，操作结果通过回调/返回值传回 |
| `handle_kg()` 直接 print | UI 无法复用 | 改为返回结构化数据（list of dicts），UI 自己渲染 |
| `_prune_merge()` 直接 print + input | 同上 | 改为生成器或回调模式 |
| 反刍引擎用 `input()` 阻塞 | UI 需要异步确认 | 改为事件/回调，UI 弹确认框 |
| batch_processor 同步运行 | 在 UI 里会卡住主线程 | 放入后台线程，通过回调通知完成 |

---
