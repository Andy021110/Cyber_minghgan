# 赛博明翰系统设计文档 V2

> 存档时间：2026-06-02  
> 状态：架构已对齐，部分已实现，部分待建设

---

## 一、系统定位

赛博明翰是一个基于真实对话提炼的**个人数字认知镜像**，不是通用 AI 助手。  
它的核心价值在于：知道你是一个什么样的人，才能给出个性化的建议和决策支持。

系统由两个功能层构成：

- **内心层（Mode 1）**：赛博明翰的心理动力图谱，自由对话，可读写
- **专项模式层（Mode 2）**：健康教练 / 学习规划 / 工作计划等，只读内心，写入决策日志

两层之间通过**水阀机制**隔离——专项模式需要"了解你"，但不能直接改写"你是谁"。

---

## 二、文件结构与物理隔离原则

```
元宝-明翰/
├── yuanbao_cyber_minghan_kg.json     # 赛博明翰内心 KG（Id/Ego/Superego）
│                                     # ⚠️ 专项模式只读，只有 Mode 1 可写
├── cyber_planner.py                  # Mode 1 入口：自由对话终端
│
├── protocols/                        # 领域协议库（静态，专项模式参考用）
│   └── bio_baseline_final.md         # Health SOP 规则（58条，已人工审查）
│
├── decision_logs/                    # 决策池（待建）
│   ├── pending.jsonl                 # 蓄水池：专项模式对话产生的待处理条目
│   ├── awaiting_approval.jsonl       # 批处理后待你审批的分类结果
│   └── health_log.jsonl             # 健康决策归档（已拍板）
│
├── pipelines/                        # 知识蒸馏工具链
│   ├── distill_health_protocol.py    # 从原始对话蒸馏 SOP 规则
│   ├── hitl_review.py                # HITL 人工审查引擎（通用）
│   └── sync_to_kg.py                 # 审查结果同步工具（当前仅 sop_rules）
│
└── archive_sources/                  # 原始对话语料（只读存档）
    └── minghan_Health_Raw_5000.md
```

**物理隔离的核心原则**：

- `yuanbao_cyber_minghan_kg.json` 是内心的唯一真相，任何流水线脚本不得在无人工审批的情况下写入
- `protocols/` 是领域规则库，与 KG 物理分离，专项模式读协议文件，不读 KG 的域数据
- `decision_logs/` 是专项模式唯一的写出口

---

## 三、已实现部分

### Mode 1 — 赛博明翰对话终端（`cyber_planner.py`）

**状态：可用**

- 四工具 Agentic Loop：`retrieve_memory` / `create_memory` / `update_memory` / `delete_memory`
- 三层心智图谱：Id（43条）/ Ego（47条）/ Superego（38条），共 128 条动力学节点
- 反刍引擎：每 5 轮对话触发，提取新特征，人工确认后写入 Ego 层
- `/` 前缀管理员指令：支持链式 Tool Use（retrieve → delete 等）
- 滚动截断：上下文超长时自动 GC，保持最近 2 轮完整历史

### Health 知识蒸馏链路

**状态：完成，产物稳定**

- 原始语料：`minghan_Health_Raw_5000.md`（100 轮对话）
- 蒸馏引擎：`distill_health_protocol.py`，13 批 × 8 轮，断点续跑
- HITL 审查：`hitl_review.py`，AI 初筛 + 人工裁决，支持二次审核
- 最终产物：`protocols/bio_baseline_final.md`，58 条规则，含 `life_context` 元数据
- KG 当前状态：`domains.Health` 已从 KG 移除，协议文件与 KG 物理隔离

### 工具链

**状态：可用，已测试**

- `hitl_review.py`：支持 `--type rules` 和 `--type nodes`，断点续审，pending 二次审核池
- `sync_to_kg.py`：支持 `--type rules` 和 `--type nodes`，原子写入

---

## 四、待建设部分

### Mode 2 — 专项模式框架

核心设计：
- 入口脚本独立（如 `health_coach.py`），不复用 `cyber_planner.py` 的对话循环
- 在 `cyber_planner.py` 中加 `/switch <mode>` 指令，单向切换，新上下文启动，历史不继承
- KG 以**只读快照**方式注入系统 prompt（不暴露写方法）
- 对应领域协议（`protocols/*.md`）全文注入

### 蓄水池与审批流

完整数据流：

```
专项模式对话
    ↓ 实时追加
pending.jsonl
    ↓ 触发条件：满 20 条 / 定时（选方案 B：自动触发）
批处理器（AI 分类路由）
    ↓
awaiting_approval.jsonl
    ↓ 下次登录 cyber_planner.py 时提示
/review 指令逐条展示
    ↓ 用户：Y/N + 个人理解（文字）
    ├→ KG 提名 → 人工确认 → 写入 Id/Ego/Superego
    └→ health_log.jsonl 直接归档
```

审批 UI 格式（终端）：

```
[1/3] 来源：健康教练 · 2026-06-03
内容：高压写代码结束后产生强烈炸鸡渴望
AI 提议：→ KG [Id 层]
理由：反映本能冲动模式，具有长期参考价值

Y 采纳 / N 拒绝 / 或直接输入你的理解
>
```

用户输入的"理解"直接成为节点的 `description`，AI 的表述被覆盖。

### 协议过期检查

每次进入专项模式时，读取协议头部 `life_context`，提示用户确认当前状态是否仍准确。  
选 N 则进入协议更新流程，选 Y 继续。不强制触发重新蒸馏。

---

## 五、设计原则与风险备忘

### 核心设计原则

1. **物理隔离优于逻辑隔离**：不同权限的数据放在不同文件里，而不是同一文件里靠代码区分
2. **流水线脚本不得直接写 KG**：任何写入 `yuanbao_cyber_minghan_kg.json` 的操作必须经过人工审批节点
3. **专项模式的唯一写出口是 `decision_logs/`**：协议文件、KG 对专项模式全部只读
4. **KG 的语义纯洁性**：Id/Ego/Superego 只存心理动力学节点，领域规则、饮食计划、学习排期不得混入

### 已识别风险与对策

| 风险 | 优先级 | 对策 | 状态 |
|------|--------|------|------|
| 模式切换上下文污染 | P1 | `/switch` 指令单向切换，历史不继承 | 待建设 |
| 专项模式污染 KG | P2 | 提名机制，写入必须经 /review 审批 | 待建设 |
| pending 池无终态 | P3 | 三出口（采纳/拒绝/过期）+ 自动批处理 | 待建设 |
| 协议过期 | P4 | 进入模式时 life_context 检查 | 待建设 |
| 日志无法利用 | P5 | 现阶段不做，schema 预留 domain+timestamp | 待观察 |

### 值得注意的历史决策

- **domains.Health 从 KG 移除（2026-06-02）**：蒸馏流水线曾直接写入 KG，破坏只读边界，已清除。Health 协议只存于 `protocols/bio_baseline_final.md`
- **63 条 KG 健康节点已清除**：未经 HITL 审查的节点不应存在于 KG，已清空。如需重建，走 `hitl_review.py --type nodes` 流程
- **`life_context` 元数据**：`bio_baseline_final.md` 头部记录了协议制定时的生活背景（体重、作息、阶段），这是协议有效期判断的依据

---

*下一步：建设 Mode 2 专项模式框架，从 Health Coach 开始*
