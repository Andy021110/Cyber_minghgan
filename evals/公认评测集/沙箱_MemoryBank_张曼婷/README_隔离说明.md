# 沙箱｜MemoryBank 张曼婷（隔离评测）

## 隔离保证

| 项目 | 路径 | 是否会被本沙箱改写 |
|------|------|-------------------|
| 赛博真图谱 | `知识蒸馏/元宝-明翰/yuanbao_cyber_minghan_kg.json` | **否**（只读指纹校验） |
| 赛博 `.env` / 代码默认行为 | 原目录 | **否**（本脚本只读 API 配置） |
| 本沙箱临时图谱 | `./kg/eval_kg_张曼婷.json` | 是（仅此处写入） |
| 跑分结果 | `./results/` | 是 |

跑前/跑后会对真图谱做 `sha256` 对比，不一致则告警。

## 测什么

MemoryBank 中文用户「张曼婷」：先把多日对话 **ingest 进临时 KG**，再问 probing 题。  
使用 **无明翰先验** 的记忆助手 prompt（不是赛博本人设）。

## 怎么跑

```bash
cd "<repo>/evals/公认评测集/沙箱_MemoryBank_张曼婷"
python3 run_memorybank_zhangmanting.py
```
