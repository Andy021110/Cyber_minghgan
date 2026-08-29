# LongMemEval 本地数据

官方可下载（不是只能在线刷分）。

- 仓库代码：https://github.com/xiaowu0162/LongMemEval
- 数据集（cleaned，推荐）：https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned
- 旧版已废弃：https://huggingface.co/datasets/xiaowu0162/longmemeval

## 三档文件

| 文件 | 大概体积 | 内容 |
|------|----------|------|
| `longmemeval_oracle.json` | ~15MB | 500 题 + 仅证据会话（最适合先看结构） |
| `longmemeval_s_cleaned.json` | ~277MB | 500 题 + ~115k token 历史 |
| `longmemeval_m_cleaned.json` | 很大 | 500 题 + ~500 sessions 历史 |

## 下载命令

```bash
mkdir -p data && cd data
# 国内可用镜像
wget https://hf-mirror.com/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json
wget https://hf-mirror.com/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json
wget https://hf-mirror.com/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_m_cleaned.json
```

本目录已下载：`longmemeval_oracle.json`（方便先翻题型）。
