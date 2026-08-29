# Handoff：从秋招迁入的记忆与续接

> 用途：换到「元宝-明翰」仓库后直接接着做评测 / 记忆迭代，不必回秋招翻产物。

## 已迁入（产品侧）

- 公开集 + 沙箱脚本 → `evals/公认评测集/`
- 产品契约 CSV / 使用说明 / MINI 跑分 → `evals/product_suite/`
- 方案与金标方法论 → `docs/evals/`
- L0 实现本就在本仓：`memory/episodic_store.py`、`episodic_tools.py`、`eval_policy.py`
- Planner 已挂 L0 工具：`cyber_planner.py`

## 关键结论（可写进面试口径）

1. **MemoryBank-CN 90/100**（L0 灌库 + 检索）  
2. **LongMemEval oracle 全量 0.808**（非 S；勿与行业 S 全量横比）  
3. **v1 修复**：`question_date` 注入、`list_episodes` 分页、更强 eval policy、judge 空 rationale 重试  
4. **badcase**：失败多为聚合/时间锚/KU/偏好与 judge 噪声，不是「没调工具」  
5. **S 分层样本 n=40 → 0.875**（未跑满 500；未跑 M）

## 隔离纪律（勿破）

- 评测临时 KG / episodic 只写沙箱目录  
- 跑前跑后校验真库 sha256  
- L1 写入保持 HITL；eval 不污染真人设

## 建议下一步（在本仓做）

1. GitHub 展示：脱敏 KG、Demo 录像、确认大 json 不入库  
2. 需要压力测再扩 LongMemEval-S 样本（先成本估算）  
3. 前端保持现有像素空间，不重做视觉

## 秋招侧刻意保留

岗位库、简历叙事、蓝标/电信事实区等求职材料 → 仍在秋招文件夹；仅产品评测与记忆工程迁到本仓。
