# Evals（赛博明翰评测中心）

本目录是公开集 / 产品契约 / 沙箱跑分的统一入口。  
秋招文件夹里的对应内容已迁移至此；请在本仓继续跑分与迭代。

## 布局

```text
evals/
├── README.md                 # 本文件
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
