# LongMemEval 轻量修复 v1 设计（方案 2）

> 日期：2026-08-12  
> 状态：已批准并进入实现  
> 原则：L0 增强 ≠ 替换 L1；真图谱只读隔离

## 目标

在保留赛博明翰 L1 动力学 KG 的前提下，增强 L0 Episodic：

1. 注入 `question_date`（解决相对时间弃权）
2. 新增 `list_episodes`（解决 top-k 漏计）
3. 强化策略：更新取最新、偏好硬约束、列举再计数
4. Judge 空 rationale / parse_error 重试
5. 评测与产品共用 tool 约定
6. 验收：103 badcase + ~50 原正确回归（seed 固定）

## 非目标

- 向量检索、LongMemEval-S/M
- 自动灌 L1、改 HITL 纪律
- 本期强制全量 500 重跑

## L0 / L1 兼容

| 层 | 文件 | 工具 | 用途 |
|----|------|------|------|
| L1 | `yuanbao_cyber_minghan_kg.json` | `retrieve_memory` 等 | 人格/动力学/HITL |
| L0 | `memory/episodic/*.jsonl` | `retrieve_episode` / `list_episodes` | 原文事实 |

评测不写真库；产品侧 L0 append 与 L1 HITL 分离。

## 验收指标

- bad 修复率（新分≥1）、改善率（新分>旧分）
- 回归：原 1 分掉到 &lt;1 的条数（目标≈0）
- 分题型修复率；isolation_ok=true
