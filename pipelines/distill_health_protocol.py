"""
distill_health_protocol.py
全量宽边界蒸馏引擎：从 archive_sources/minghan_Health_Raw_5000.md 提纯机体协议。

双轨输出：
  轨1 (SOP 宽边界)  — 防止机体受到严重负面影响的宏观防线（非微观管理）
  轨2 (KG Nodes)    — 压力/触发事件 → 生理偏好/心理欲望的因果节点

终态落盘：
  sop_rules → protocols/bio_optimization_baseline.md  (去重后 Markdown)
  kg_nodes  → yuanbao_cyber_minghan_kg.json           (追加进现有 KG)

用法:
    python3 pipelines/distill_health_protocol.py            # 全量运行
    python3 pipelines/distill_health_protocol.py --dry-run  # 只打印批次划分，不调 API
    python3 pipelines/distill_health_protocol.py --batch 0  # 只跑单个批次（调试用）
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── 路径常量 ──────────────────────────────────────────────────────
ROOT          = Path(__file__).parent.parent
MD_PATH       = ROOT / "archive_sources" / "minghan_Health_Raw_5000.md"
KG_PATH       = ROOT / "yuanbao_cyber_minghan_kg.json"
SOP_PATH      = ROOT / "protocols" / "bio_optimization_baseline.md"
PROGRESS_PATH = ROOT / "protocols" / "health_distill_progress.json"

BATCH_SIZE    = 8     # 每批对话轮次数（控制单次 API 输出 token ≤1000）
SLEEP_BETWEEN = 2.0   # 批次间休眠秒数，防止 API 熔断
MAX_RETRIES   = 3     # 单批次最大重试次数

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("health_distiller")


# ══════════════════════════════════════════════════════════════════
#  Prompt 定义
# ══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
你是一位冷静的机体协议架构师，负责从用户与健康 AI 的对话中提炼宏观防线与心理因果节点。

【轨1 SOP 宽边界规则】
- 目标：提取"防止机体受到严重负面影响的宏观防线"，绝不微观管理。
- 红线应覆盖一整类行为的上/下限，而非某次具体行为。
- 正确示例：
    · "咖啡因日摄入上限 400mg（约4杯标准美式），超出后睡眠质量显著下降"
    · "每日净摄入热量不得低于 1200kcal，否则触发代谢保护性降速"
    · "连续久坐不超过 90 分钟，需插入 ≥5 分钟站立或行走"
- 错误示例（微观管理，禁止）：
    · "下午3点后不喝咖啡"  → 应改写为摄入上限+时间窗口建议
    · "今天午饭只吃半碗饭" → 具体餐次管理，不属于宏观防线

【轨2 KG 节点（因果链）】
- 目标：提取用户的压力/触发事件 → 生理偏好或心理欲望之间的因果节点。
- 关注：情绪压力如何映射为特定食物渴望、作息偏移或回避行为。

【输出格式】
严格输出 JSON，禁止附加任何说明文字：
{
  "sop_rules": ["宏观防线1", "宏观防线2"],
  "kg_nodes": [
    {
      "node_id": "health_trigger_xxx",
      "category": "health_psychology",
      "trigger": "触发事件（压力源/情境）",
      "reaction": "生理偏好或心理欲望的具体表现"
    }
  ]
}
每批最多输出 5 条 sop_rules、5 条 kg_nodes。"""

USER_TMPL = """\
以下是赛博明翰与健康 AI 的对话片段，共 {n} 个完整回合（第 {start}–{end} 轮）：

{text}

请严格按 System 中定义的 JSON 格式输出，不要有任何额外文字。"""


# ══════════════════════════════════════════════════════════════════
#  模块 1 — Parser
# ══════════════════════════════════════════════════════════════════

def chunk_by_turn(text: str) -> list[str]:
    """按 '# you asked' 切分对话轮次。"""
    boundaries = [m.start() for m in re.finditer(r"^# you asked", text, re.MULTILINE)]
    if not boundaries:
        return []
    turns = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        turns.append(text[start:end].strip())
    return turns


# ══════════════════════════════════════════════════════════════════
#  模块 2 — Distiller（单批次 API 调用）
# ══════════════════════════════════════════════════════════════════

def _strip_code_fence(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def distill_batch(
    turns: list[str],
    batch_idx: int,
    client: anthropic.Anthropic,
) -> dict:
    """
    对一批 turns 调用 API 做双轨蒸馏。
    失败时重试 MAX_RETRIES 次，全部失败返回空结构。
    """
    start_turn = batch_idx * BATCH_SIZE + 1
    end_turn   = start_turn + len(turns) - 1
    combined   = "\n\n---\n\n".join(turns)
    user_msg   = USER_TMPL.format(
        n=len(turns), start=start_turn, end=end_turn, text=combined
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model=os.environ.get("MODEL", "deepseek-v4-pro"),
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = _strip_code_fence(resp.content[0].text)
            result = json.loads(raw)
            logger.info(
                "[Distiller] Batch%d OK — SOP:%d KG:%d",
                batch_idx,
                len(result.get("sop_rules", [])),
                len(result.get("kg_nodes", [])),
            )
            return result
        except json.JSONDecodeError as e:
            logger.warning("[Distiller] Batch%d JSON 解析失败（尝试 %d/%d）: %s", batch_idx, attempt, MAX_RETRIES, e)
        except Exception as e:
            logger.warning("[Distiller] Batch%d API 错误（尝试 %d/%d）: %s", batch_idx, attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(5 * attempt)

    logger.error("[Distiller] Batch%d 全部重试失败，跳过", batch_idx)
    return {"sop_rules": [], "kg_nodes": []}


# ══════════════════════════════════════════════════════════════════
#  模块 3 — Merger（终态去重与物理合拢）
# ══════════════════════════════════════════════════════════════════

def dedup_sop_rules(rules: list[str]) -> list[str]:
    """
    去重：规范化（去空格、转小写）后按前 12 字做指纹去重，
    保留首次出现的完整原文。
    """
    seen: set[str] = set()
    result: list[str] = []
    for r in rules:
        key = re.sub(r"\s+", "", r).lower()[:12]
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def dedup_kg_nodes(nodes: list[dict]) -> list[dict]:
    """按 trigger 前 10 字做指纹去重。"""
    seen: set[str] = set()
    result: list[dict] = []
    for n in nodes:
        key = re.sub(r"\s+", "", n.get("trigger", "")).lower()[:10]
        if key not in seen:
            seen.add(key)
            result.append(n)
    return result


def write_sop_markdown(rules: list[str], out_path: Path) -> None:
    """将去重后的 sop_rules 写入 Markdown 文件。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# 机体优化基线协议（Bio Optimization Baseline）",
        "",
        f"> 自动蒸馏生成 · {now}  ",
        f"> 来源：`{MD_PATH.name}`  ",
        f"> 规则总计：{len(rules)} 条",
        "",
        "---",
        "",
        "## SOP 宏观防线",
        "",
    ]
    for i, rule in enumerate(rules, 1):
        lines.append(f"{i}. {rule}")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("[Merger] SOP Markdown 已写入：%s（%d 条）", out_path, len(rules))


def append_kg_nodes(nodes: list[dict], kg_path: Path) -> None:
    """将去重后的 kg_nodes 追加到 yuanbao_cyber_minghan_kg.json。"""
    if not kg_path.exists():
        logger.error("[Merger] KG 文件不存在：%s", kg_path)
        return

    kg = json.loads(kg_path.read_text(encoding="utf-8"))

    # 确保 Health_Nodes 容器存在
    node_bucket = kg.setdefault("nodes", {}).setdefault("Cyber_Minghan", {})
    existing = node_bucket.setdefault("Health_Nodes", [])

    # 对照已有 trigger 去重
    existing_keys = {
        re.sub(r"\s+", "", n.get("trigger", "")).lower()[:10]
        for n in existing
    }

    added = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for n in nodes:
        key = re.sub(r"\s+", "", n.get("trigger", "")).lower()[:10]
        if key not in existing_keys:
            n.setdefault("uuid", uuid.uuid4().hex)
            n.setdefault("created_at", now_iso)
            n["source"] = "health_distillation"
            existing.append(n)
            existing_keys.add(key)
            added += 1

    kg["updated_at"] = now_iso

    # 原子写入
    tmp = kg_path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(kg_path)
    logger.info("[Merger] KG 追加完成：新增 %d 条 Health_Nodes，跳过 %d 条重复", added, len(nodes) - added)


# ══════════════════════════════════════════════════════════════════
#  模块 4 — Orchestrator
# ══════════════════════════════════════════════════════════════════

def _load_progress() -> dict:
    """读取进度文件，返回 {batch_idx_str: {sop_rules, kg_nodes}}。"""
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_progress(progress: dict) -> None:
    """原子写入进度文件。"""
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


class Orchestrator:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.client  = None if dry_run else anthropic.Anthropic()

    def run(self, target_batch: Optional[int] = None) -> None:
        logger.info("[Orchestrator] 读取语料：%s", MD_PATH)
        text  = MD_PATH.read_text(encoding="utf-8")
        turns = chunk_by_turn(text)
        logger.info("[Orchestrator] 共 %d 个对话轮次", len(turns))

        batches = [
            turns[i : i + BATCH_SIZE]
            for i in range(0, len(turns), BATCH_SIZE)
        ]
        logger.info("[Orchestrator] 共 %d 个批次（每批 %d 轮）", len(batches), BATCH_SIZE)

        if self.dry_run:
            for idx, b in enumerate(batches):
                start = idx * BATCH_SIZE + 1
                end   = start + len(b) - 1
                print(f"  Batch{idx:02d}  轮次 {start:>3}–{end:<3}  ({len(b)} 轮)")
            return

        if target_batch is not None:
            if target_batch >= len(batches):
                logger.error("批次索引 %d 超出范围（共 %d 批）", target_batch, len(batches))
                return
            self._run_single(target_batch, batches[target_batch])
            return

        # 全量运行：每批立即落盘，支持断点续跑
        progress = _load_progress()
        succeeded = skipped = 0

        for idx, batch in enumerate(batches):
            key = str(idx)
            if key in progress:
                logger.info("[Orchestrator] Batch%d 已有缓存，跳过", idx)
                skipped += 1
                continue

            result = distill_batch(batch, idx, self.client)
            progress[key] = result
            _save_progress(progress)
            logger.info(
                "[Orchestrator] Batch%d 已落盘 → %s",
                idx, PROGRESS_PATH.name,
            )
            succeeded += 1

            if idx < len(batches) - 1:
                time.sleep(SLEEP_BETWEEN)

        logger.info(
            "[Orchestrator] 全量完成：%d 批成功，%d 批跳过（断点续跑）",
            succeeded, skipped,
        )
        self._merge_and_persist(progress)

    def _run_single(self, idx: int, batch: list) -> None:
        """单批次调试运行，只打印结果，不落盘。"""
        result = distill_batch(batch, idx, self.client)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    def _merge_and_persist(self, progress: dict) -> None:
        all_sop: list = []
        all_kg:  list = []
        for key in sorted(progress.keys(), key=lambda x: int(x)):
            batch_result = progress[key]
            all_sop.extend(batch_result.get("sop_rules", []))
            all_kg.extend(batch_result.get("kg_nodes",  []))

        deduped_sop = dedup_sop_rules(all_sop)
        deduped_kg  = dedup_kg_nodes(all_kg)

        logger.info(
            "[Orchestrator] 去重后：SOP %d 条（原 %d），KG %d 条（原 %d）",
            len(deduped_sop), len(all_sop),
            len(deduped_kg),  len(all_kg),
        )

        write_sop_markdown(deduped_sop, SOP_PATH)
        append_kg_nodes(deduped_kg, KG_PATH)

        print("\n" + "═" * 60)
        print(f"SOP 宏观防线（{len(deduped_sop)} 条）：")
        for r in deduped_sop:
            print(f"  · {r}")
        print(f"\nKG 健康节点（{len(deduped_kg)} 条）：")
        for n in deduped_kg[:5]:
            print(f"  [{n.get('node_id')}]")
            print(f"    trigger  → {n.get('trigger')}")
            print(f"    reaction → {n.get('reaction')}")
        if len(deduped_kg) > 5:
            print(f"  ... 还有 {len(deduped_kg) - 5} 条，详见 KG 文件")
        print("═" * 60)
        print("✓ 蒸馏完成")


# ══════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Health Distiller — 全量宽边界蒸馏引擎")
    ap.add_argument("--dry-run", action="store_true", help="只打印批次划分，不调用 API")
    ap.add_argument("--batch",   type=int, default=None, help="只运行单个批次（索引从 0 开始），结果打印到终端")
    args = ap.parse_args()

    Orchestrator(dry_run=args.dry_run).run(target_batch=args.batch)


if __name__ == "__main__":
    main()
