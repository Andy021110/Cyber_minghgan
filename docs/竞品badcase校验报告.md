# 竞品 badcase 校验报告

> 日期：2026-08-30 · 用途：用**别人踩过的坑**校验自己的实现
> 用例集：`evals/competitive/cases.jsonl`　跑法：
> `.venv/bin/python -m evals.replay --path evals/competitive/cases.jsonl`

## 1. 方法与来源

调研了同类记忆/个人 Agent 的已知失败模式（Mem0、Zep/Graphiti、Letta/memGPT、
Generative Agents、Second Me、Hermes、ChatGPT/Claude Memory），
来源包括官方 GitHub issue、论文 failure taxonomy（MemFail、LongMemEval、
LoCoMo、PerLTQA、MemoryAgentBench、MINJA、Trojan Hippo）与从业者复盘，
共整理 35 条，**每条都标注了来源与一手/二手**。

收录原则（重要）：**只把能在我们的实现上自动跑的做成用例**。
需要 LLM 抽取层或写入端的（如条件限定丢失、记忆投毒）不塞进自动化集
冒充覆盖率，单独列在第 3 节说明。

## 2. 自动化校验结果（8 条）

| ID | 竞品来源 | 我们的结果 |
|---|---|---|
| COMP-01 | MemFail #8 共存事实（图记忆在此类 fails spectacularly） | **pass** |
| COMP-02 | MemFail #15 误导性查询（52.3% 查询是误导性的） | fail ⚠️环境限制 |
| COMP-03 | LongMemEval Abstention（该弃权时编一个） | fail ⚠️环境限制 |
| COMP-04 | 通用词汇鸿沟 | **fail** ← 真实缺口 |
| COMP-05 | 本项目 L0 私密原文外泄 | **pass**（修复后） |
| COMP-06 | 本项目 interactions 死数据 | pass |
| COMP-07 | 门槛误杀短查询（本项目修复的副作用风险） | pass |
| COMP-08 | 对外 public 应可召回（防空集假通过） | pass |

### 关于 COMP-02/03 的 fail

这两条用临时小 KG（1–2 节点）测弃权，而 `kw_abstain_min_corpus=20`
意味着**小语料下弃权门槛不启用**，因此必然 fail——这是测试环境限制，
不是实现缺陷。真实 KG（146 节点）上实测无答案问题 **4/5 正确弃权**
（见 `tests/test_retrieval_scoring.py::test_unanswerable_query_abstains`）。
**结论以大语料为准**，用例里已标注 `known_limitation`。

### 关于 COMP-04

这是唯一确认的真实缺口：问「咖啡」召回不到「美式」。
字符 n-gram 只能解决用词重叠，跨不过同义替换。**必须有语义向量**。
已单列为 BC-010。本次尝试装 sentence-transformers（成功），
但 `huggingface.co` 与 `hf-mirror.com` **均不可达**，模型拉不到，
因此 BC-010 保持 open（环境阻塞，非设计问题）。

## 3. 未纳入自动化集（附理由，不冒充覆盖）

| 竞品失败模式 | 为什么没自动化 |
|---|---|
| 条件限定在压缩中丢失（MemFail #18） | 需要 LLM 抽取层，我们的 KG 由人工/LLM 构建而非自动抽取，失败路径不同 |
| 可变属性无 supersession（Mem0 #1、#3） | 我们**有** `memory/versioning.py` 但从未接入写入路径（BC-005），属已知缺口而非可测用例 |
| 谄媚放大 25×（arXiv 2606.10949） | 需多轮 LLM 交互与评测基准，非单机可跑 |
| 记忆投毒 / 休眠 payload（MINJA、Trojan Hippo、AgentPoison） | 需攻击链路构造；我们的写入端不做来源可信度区分，是**真实缺口**（见第 4 节） |
| 遗忘曲线无消融（MemoryBank） | 我们同样未标定（`last_accessed_at` 120/146 为空，遗忘退化为按创建时间衰减） |
| 重复写入导致 97% 垃圾条目（Mem0 #27） | 我们没有写入去重，是真实缺口 |
| 多跳长程因果链（MemFail #9） | 需构造长链语料，与共存事实用例重叠度高，暂不重复建设 |

## 4. 结论：相对竞品的已知缺口

按「我们是否已经存在同类问题」排序，这些都是**尚未登记为 badcase 的**：

1. **写入端不区分来源可信度** —— 竞品里最严重的一类（MINJA 98.2% 注入成功率、
   Trojan Hippo 跨越 100 个会话后触发）。我们的记忆写入同样不校验来源。
2. **无写入去重** —— 同一事实换措辞重复存（竞品实测同一条存了 47 次）。
3. **supersession 未接入** —— 与 Mem0 的 ADD-only 同类问题（BC-005 已登记）。
4. **遗忘参数未标定** —— 与 MemoryBank 同类（有实现、无消融证据）。

前两条是本次调研的**新发现**，建议登记为 badcase。

## 5. 本次调研顺带修正的两个认知

- **不要只看"命中率"数字**：初始 2-gram 把命中从 0 提到 24，看着很好，
  但抽查发现无答案问题照样召回一堆噪声——命中数多不等于召回对。
  加 IDF 后才真正可用。
- **阈值会依赖语料规模**：0.8 是按 146 篇的分布标定的，
  小语料上 IDF 全退化成 1 会误杀一切。已加 `kw_abstain_min_corpus` 处理。
