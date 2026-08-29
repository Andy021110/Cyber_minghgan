# Evals（赛博明翰评测中心）

本目录是公开集 / 产品契约 / 沙箱跑分的统一入口。  
秋招文件夹里的对应内容已迁移至此；请在本仓继续跑分与迭代。

## 布局

```text
evals/
├── README.md                 # 本文件
├── badcases.py               # Badcase 登记处（自包含 reproduce）
├── badcases/cases.jsonl      # 缺陷台账（BC-001…）
├── replay.py                 # 回放器：把失败样本变成可执行的回归测试
├── health.py                 # 工作流自身的健康度指标
├── retrieval_ab.py           # 检索 A/B（Recall@k / MRR@k）
├── product_suite/            # 自建契约集 CSV + 使用说明 + 历史跑分
├── 公认评测集/                # LongMemEval / MemoryBank / PerLTQA + 沙箱
│   ├── 00_索引与用法.md
│   ├── LongMemEval/
│   ├── MemoryBank/
│   ├── PerLTQA/
│   ├── 沙箱_LongMemEval/
│   ├── 沙箱_MemoryBank_张曼婷/
│   └── 沙箱_能力契约_MINI/
└── LongMemEval_legacy/       # 历史副本（可选）
```

方法论文档在 [`docs/evals/`](../docs/evals/)。

## 实验驱动开发：三件套

自主探索（Agent loop / harness）下，绝大多数决策都不是「对或错」，
而是「合不合理」——要靠实验定。三个工具各回答一个问题：

| 问题 | 工具 | 命令 |
|------|------|------|
| 这个决策凭什么这么定？ | `experiments/ledger.py` | `python3 -m experiments.ledger` |
| 已修的缺陷有没有复发？ | `evals/replay.py` | `python3 -m evals.replay` |
| 这套工作流本身高不高效？ | `evals/health.py` | `python3 -m evals.health` |

### 判定语义（replay）

| 登记状态 | 回放结果 | 判定 | 含义 |
|----------|----------|------|------|
| fixed | pass | OK | 修复被守住 |
| fixed | fail | **REGRESSION** | 已修的又坏了，退出码 1 阻断 CI |
| open | fail | OPEN | 已知缺陷仍在 |
| open | pass | RECHECK | 标着未修却能过，需人工核对 |
| — | — | MANUAL | 无法自动验证 |

**MANUAL 不是好事**：它意味着「没检查」，而不是「没问题」。
`health.py` 会把覆盖率报出来，防止「无回归」变成自欺。

### 登记一条 badcase

```python
from evals.badcases import add_case
add_case({
    "type": "retrieval",           # retrieval / answer / infra / quality
    "title": "中文整句做关键词检索必然失配",
    "reproduce": {                  # 必须自包含：不依赖真实 KG
        "source": "l0",             # l0 原文记忆 / l1 动力学 KG
        "seed": [{"ts": "2026-03-11", "user_text": "我平时只喝美式",
                  "assistant_text": "记住了"}],
        "query": "你还记得我喜欢喝什么咖啡吗",
        "must_contain": "美式",      # 或 must_not_contain（泄漏类缺陷）
    },
    "root_cause": "...", "fix_ref": "C3",
})
```

修好之后**必须**补 `regression_test`（pytest / vitest node id），
否则它永远停在 MANUAL——标为 fixed 却无法验证，等于没修。

### 实验台账：先登记假设，再动手

```python
from experiments.ledger import propose, conclude
exp = propose(hypothesis="提高 λ 能提升 Recall@5",
              change="hybrid λ 0.4→0.6", metric="Recall@5", baseline=0.62)
# ... 跑实验 ...
conclude(exp["id"], result=0.71, decision="adopt", note="语义召回补足明显")
```

顺序不能反。先跑后补假设的话，谁都会给已做的改动编个合理理由——
那是确认偏误，不是实验。

## 跑分前约定

1. **不写真图谱**：沙箱脚本启动时校验 `yuanbao_cyber_minghan_kg.json` 的 sha256。  
2. **路径已相对化**：脚本用 `Path(__file__)` 定位仓库根与数据，无需改绝对路径。  
3. **密钥**：在仓库根 `.env` 配置 DeepSeek / Anthropic-compatible API。  
4. **大文件**：`longmemeval_s_cleaned.json` ~265MB，默认建议不入库（见根 `.gitignore`）；缺文件时从官方 HF 下载。

## 常用命令（在对应沙箱目录）

```bash
# MemoryBank-CN 全量（历史口径 90/100）
cd evals/公认评测集/沙箱_MemoryBank_张曼婷
python3 run_v3_all_memorybank_cn.py

# LongMemEval oracle 全量 / 续跑
cd evals/公认评测集/沙箱_LongMemEval
python3 run_longmemeval_oracle_full.py

# LongMemEval-S 分层抽样
python3 run_longmemeval_s_sample.py

# 产品契约 MINI
cd evals/公认评测集/沙箱_能力契约_MINI
python3 run_mini_abc.py
```

## 对外报分口径（摘要）

| Benchmark | Setting | Result |
|-----------|---------|--------|
| MemoryBank-CN | 100 Q · L0 | 90/100 |
| LongMemEval | oracle full 500 | 0.808 |
| LongMemEval | S sample n=40 | 0.875 |
| MINI | Abstain / Faith / Update | 10/10 · 8/10 · 4/5 |

Oracle ≠ S/M；勿与厂商 S 全量榜直接横比。详见根 [`README.md`](../README.md) §6。

## 从秋招迁入的内容

| 原位置（秋招/补洞产物） | 现位置 |
|-------------------------|--------|
| `公认评测集/` | `evals/公认评测集/` |
| `赛博_评测集_*.csv` 等 | `evals/product_suite/` |
| `赛博明翰_*.md` / 金标方法论 | `docs/evals/` |
| `LongMemEval/` 旧副本 | `evals/LongMemEval_legacy/` |
| `跑分结果/` | `evals/product_suite/跑分结果/` |

秋招侧简历 / 岗位库里的「赛博明翰叙事」仍留在秋招仓，不迁产品代码。
