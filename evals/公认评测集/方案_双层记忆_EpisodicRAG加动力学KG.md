# 双层记忆方案：L0 Episodic RAG + L1 动力学 KG

> **For agentic workers:** 实现时按文末 Task 清单逐步做；评测仍只写沙箱，不碰真图谱。  
> 日期：2026-08-12

**Goal:** 在保留 Id/Ego/Superego 心智层的同时，补上「原文事实可检索」的第一层，使 MemoryBank 类事实题可达标，且不牺牲空库拒答/HITL 写入纪律。

**Architecture:**  
- **L0 Episodic**：按轮次追加的对话/事实卡片，检索用轻量 RAG（先关键词/BM25，可选向量）。  
- **L1 Dynamics**：现有三层图谱，只存提炼后的模式与人审通过的节点。  
- **路由**：事实题优先 L0；人格/动机/模式题走 L1；可并行后由模型综合。

**Tech Stack:** Python · 现有 `cyber_planner.CyberBrainStore` · 新增 `EpisodicStore`（JSONL）· 评测复用 MemoryBank 张曼婷 7 题 · DeepSeek Anthropic 兼容口

---

## 0. 为什么加 L0

| 层 | 存什么 | 擅长 | 弱点 |
|----|--------|------|------|
| L0 Episodic RAG | 原文 turn / 事实槽 | 电影名、画家、日期事件 | 噪声、难抽象 |
| L1 动力学 KG | 提炼节点 | 画像、动机、HITL 纪律 | 事实保真下降 |

MemoryBank 证明：只用 L1 蒸馏，事实题会掉（V2 4/7）。  
目标不是扔掉 L1，而是 **L0 保事实，L1 保心智**。

---

## 1. 目标结构

```text
用户问题
   │
   ├─ retrieve_episode  →  L0 原文片段（事实）
   └─ retrieve_memory   →  L1 Id/Ego/Superego（模式）
   │
   └─ 模型综合作答（禁止无检索编造）
```

写入路径：

```text
每轮对话 ──append──► L0 episodic.jsonl   （默认自动，可审计）
     │
     └─ 反刍/批处理筛选 ──HITL──► L1 KG   （只留值得沉淀的）
```

**原则：** L0 不替代 HITL；L0 是「记得说过什么」，L1 是「这改变了我是谁」。

---

## 2. L0 数据模型（最小可用）

文件（沙箱示例）：  
`沙箱_*/kg/episodic_<user>.jsonl`  
产品侧建议：`元宝-明翰/memory/episodic/<user_id>.jsonl`

每行一条：

```json
{
  "eid": "ep_20230503_002",
  "ts": "2023-05-03",
  "role_user": "用户",
  "role_assistant": "助手",
  "user_text": "...",
  "assistant_text": "...",
  "text": "日期:2023-05-03\n用户:...\n助手:...",
  "entities": ["达·芬奇", "米开朗基罗", "拉斐尔"],
  "source": "MemoryBank|live"
}
```

- `text`：检索主字段（全文）  
- `entities`：可选，抽取专名，提升命中  
- **不做** 80 字截断；返回给模型至少 top-k 全文

### L0 检索（V1 不做向量也行）

1. 查询归一：`5月4日` → `2023-05-04` / `5月4日` 多键  
2. 打分：关键词命中 + 专名命中 + 最近日期加成  
3. 返回 top-k（默认 5）完整 `text`

V2 再加 embedding（可选），不作为第一期门槛。

---

## 3. 怎么接到赛博（代码落点）

| 组件 | 建议路径 | 职责 |
|------|----------|------|
| EpisodicStore | `元宝-明翰/memory/episodic_store.py` | append / search |
| Tool | `cyber_planner.py` 增 `retrieve_episode` | 事实检索 |
| 写入 | 对话 loop 每轮 user+assistant 后 `episodic.append` | 自动 |
| System prompt | 事实偏好/经历/日期 → **先** `retrieve_episode`；模式/动机 → `retrieve_memory` | 路由说明 |
| 评测沙箱 | `沙箱_MemoryBank_张曼婷/run_v3_dual_memory.py` | L0+L1 对比实验 |

**HITL / batch_processor / build_kg：** 仍只写 L1；不要求每条原文进图谱。

---

## 4. 路由策略（达成「像产品」）

```text
if 问具体专名/某日事件/「我说过什么」:
    must retrieve_episode
    optional retrieve_memory
elif 问性格模式/为什么/倾向:
    must retrieve_memory
    optional retrieve_episode
elif 空库/无命中:
    abstain + 追问（两边都空才算真没有）
```

空库 Abstain 定义更新为：**L0 与 L1 皆空（或皆无相关）→ 拒答**。  
避免「L1 空但 L0 有」时误拒答。

---

## 5. 怎么样算达成目标（验收门槛）

### P0 必须过（否则不算加上）

| ID | 指标 | 门槛 | 测法 |
|----|------|------|------|
| G1 | MemoryBank 张曼婷 7 题 | **≥ 6/7**（理想 7/7） | 沙箱 V3，L0+L1，隔离 True |
| G2 | 相对 V2（仅 L1） | **严格更高**（至少 +2 题或 ≥6） | 同题对比 JSON |
| G3 | 画家 / 出租车司机 / 5·4 麻烦 | **三题全过**（曾失败的硬点） | case 级 |
| G4 | 真图谱不污染 | isolation sha256 不变 | 指纹 |
| G5 | 空库拒答不回退 | MINI-A 抽样 ≥ 上次协议下可接受 | 空 L0+空 L1 测 5 题 |

### P1 加分（可第二周）

| ID | 指标 | 门槛 |
|----|------|------|
| G6 | MemoryBank 再扩 2 用户 | 每人 ≥ 5/7 或均值 ≥ 0.75 |
| G7 | L1 仍有写入 | 反刍/筛选后 L1 节点数 > 0（证明没废弃动力学层） |
| G8 | 延迟 | 单题 p95 < 30s（工具轮次可控） |

### 明确不作为本期目标

- 不上 LongMemEval-S 全量  
- 不上向量库标配  
- 不改真库明翰人设灌 MemoryBank  

---

## 6. 实验对照（报告怎么写）

同一用户张曼婷、同一 7 题：

| 条件 | 预期 |
|------|------|
| A 仅糙灌 L1（旧） | ~6/7 但无动力学语义 |
| B 仅蒸馏 L1（V2） | 4/7 |
| C **L0+L1（本方案）** | ≥6/7，且 G3 三题过 |
| D 仅 L0 | 应接近 C；若 C≈D，说明 L1 未帮事实题（可接受，L1 另有职责） |

对外话术：

> 记忆分情景层（RAG）与心智层（三层图谱）；公开事实集主要验收情景层，心智层用人审与画像契约验收。

---

## 7. 实施任务清单

### Task 1: EpisodicStore MVP

- Create: `元宝-明翰/memory/episodic_store.py`
- Create: `元宝-明翰/memory/README.md`（L0/L1 边界）
- [ ] append / search（关键词）
- [ ] 日期归一简易规则
- [ ] 单测：写入 2 轮，用「达芬奇」能搜回

### Task 2: 沙箱 V3 双层评测（先于改线上）

- Create: `沙箱_MemoryBank_张曼婷/run_v3_dual_memory.py`
- [ ] MemoryBank history → L0 append 全量  
- [ ] 可选：同步跑现有 V2 抽取写 L1（或复用 v2 kg）  
- [ ] tools: `retrieve_episode` + `retrieve_memory`  
- [ ] 输出 `v3_dual_*.json`（含 started_at/finished_at）  
- [ ] 达标判定打印 G1–G4

### Task 3: 接 cyber_planner（产品路径）

- Modify: `cyber_planner.py`（CYBER_TOOLS + `_dispatch_tool` + prompt）
- [ ] 每轮结束后 append L0（路径可配置，默认用户目录）  
- [ ] 评测/开发可用 `EPISODIC_PATH` 指到沙箱  
- [ ] 真库默认 L0 与 L1 分文件，避免混写

### Task 4: 回归 Abstain

- [ ] 空 L0+空 L1 跑 MINI-A 5 题  
- [ ] 确认无「靠人设先验答北邮」

### Task 5: 结论页

- Create: `补洞产物/赛博_双层记忆_P0结论.md`
- [ ] 对照表 A/B/C + badcase + 是否宣布 P0 达成

---

## 8. 建议落地顺序（你问「怎么加」）

1. **先做 Task 2 沙箱 V3**（1 晚）：不动真库，验证 G1–G4  
2. 过了再 Task 1+3 进产品代码  
3. 最后 Task 4–5 写结论  

若 V3 上 G3 仍挂：优先查 L0 是否含原文，而不是先上向量。

---

## 9. 一句话验收

> **加上 L0 且算达成 = 张曼婷 7 题 ≥6/7，且画家/出租车司机/5·4 三题全过，真库指纹不变，空库拒答不回退。**
