"""
batch_processor.py — 蓄水池批处理器（Phase 4）

读取 pending.jsonl 中所有 status="pending" 的条目，
用 AI 分类路由（KG 提名 or 领域日志），
结果写入 awaiting_approval.jsonl，pending 状态更新为 "processing"。

用法：
    python3 pipelines/batch_processor.py          # 正式运行
    python3 pipelines/batch_processor.py --dry-run # 只打印分类结果，不落盘
"""

import json
import re
import sys
import time
import argparse
import logging
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipelines"))

load_dotenv(ROOT / ".env")

from decision_log import (
    read_pending,
    update_pending_status,
    write_approval_item,
    write_notification,
)

BATCH_SIZE  = 5
MAX_RETRIES = 3
SLEEP_SEC   = 1.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("batch_processor")

_GREEN = "\033[92m"
_GRAY  = "\033[90m"
_RESET = "\033[0m"


# ══════════════════════════════════════════════════════════════════
#  分类 Prompt
# ══════════════════════════════════════════════════════════════════

_CLASSIFY_SYSTEM = """\
你是赛博明翰心智图谱的分类路由员。

收到一批来自专项模式对话的观察条目，判断每条的归属：

【kg — 适合写入心智图谱】
- 反映深层心理模式、本能冲动、防御机制
- 有触发条件→反应的因果结构，具有长期稳定性
- 例：「高压写代码时逃跑冲动被奶茶激活」

【log — 适合写入领域日志】
- 具体的饮食/健康决策记录，当次行为选择
- 协议执行情况，不代表稳定的心理模式
- 例：「今天下午喝了一杯 3 分糖奶茶」

layer（仅 route=kg 时填写）：
- Id：本能欲望、即时快感、逃避冲动
- Ego：现实协商、防御机制、延迟满足
- Superego：道德约束、自我批判、规范内化

importance（1-10，仅 route=kg 时填写）：
- 9-10：核心身份认同、重要关系、长期稳定的根本性模式
- 7-8：有充分证据的稳定模式，对理解人格有明显价值
- 5-6：中等强度模式，证据中等或模式可能随时间变化
- 3-4：单次观察推测，证据薄弱，可能是偶发现象
- 1-2：高度不确定，几乎无证据支撑

输出严格 JSON 数组（禁止任何额外文字）：
[
  {
    "id": "条目原始id",
    "route": "kg 或 log",
    "layer": "Id 或 Ego 或 Superego 或 null",
    "rationale": "分类理由，不超过 20 字",
    "importance": <1-10整数，依据上方标准判断，单次观察3-4，稳定模式7-8>,
    "importance_note": "重要度说明，不超过 15 字（route=log 时填 null）"
  }
]"""


def _format_batch_for_prompt(entries: list) -> str:
    lines = []
    for e in entries:
        lines.append(
            f"id: {e['id']}\n"
            f"来源: {e.get('source_mode', '')}\n"
            f"内容: {e.get('content', '')}\n"
            f"证据: {e.get('raw_evidence', '')}\n"
        )
    return "\n---\n".join(lines)


def classify_batch(entries: list, client: anthropic.Anthropic) -> list:
    """
    对一批 pending 条目调用 AI 分类。
    返回 [{id, route, layer, rationale}, ...] 或空列表（失败时）。
    """
    user_msg = f"以下是 {len(entries)} 条待分类观察：\n\n{_format_batch_for_prompt(entries)}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_CLASSIFY_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = re.sub(r"^```(?:json)?\s*", "", resp.content[0].text.strip())
            raw = re.sub(r"\s*```$", "", raw).strip()
            result = json.loads(raw)
            logger.info("[Classifier] batch OK — %d 条已分类", len(result))
            return result if isinstance(result, list) else []
        except json.JSONDecodeError as e:
            logger.warning("[Classifier] JSON 解析失败（尝试 %d/%d）: %s", attempt, MAX_RETRIES, e)
        except Exception as e:
            logger.warning("[Classifier] API 错误（尝试 %d/%d）: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)

    logger.error("[Classifier] 全部重试失败，本批跳过")
    return []


# ══════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════

def run(dry_run: bool = False) -> int:
    """
    执行批处理。
    返回写入 awaiting_approval 的条目数。
    """
    pending = read_pending(status="pending")
    if not pending:
        logger.info("[BatchProcessor] 蓄水池为空，无需处理")
        return 0

    logger.info("[BatchProcessor] 待处理条目：%d 条", len(pending))

    client = None if dry_run else anthropic.Anthropic()

    # 按 BATCH_SIZE 切批
    batches = [pending[i: i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    total_written = 0

    for batch_idx, batch in enumerate(batches):
        logger.info("[BatchProcessor] Batch %d/%d（%d 条）", batch_idx + 1, len(batches), len(batch))

        if dry_run:
            for e in batch:
                print(f"  [DRY-RUN] id={e['id'][:8]}… content={e['content'][:40]}")
            continue

        results = classify_batch(batch, client)

        # 建立 id → 原始 entry 的映射
        entry_map = {e["id"]: e for e in batch}

        for r in results:
            entry_id = r.get("id")
            orig = entry_map.get(entry_id)
            if not orig:
                logger.warning("[BatchProcessor] 返回了未知 id：%s，跳过", entry_id)
                continue

            route     = r.get("route", "log")
            layer     = r.get("layer") if route == "kg" else None
            rationale = r.get("rationale", "")
            importance      = r.get("importance", 5) if route == "kg" else None
            importance_note = r.get("importance_note") if route == "kg" else None

            # 写入 awaiting_approval
            write_approval_item(
                pending_id=entry_id,
                source_mode=orig.get("source_mode", ""),
                content=orig.get("content", ""),
                raw_evidence=orig.get("raw_evidence", ""),
                proposed_route=route,
                proposed_layer=layer,
                ai_rationale=rationale,
                importance=importance,
                importance_note=importance_note,
            )

            # 更新 pending 状态为 processing
            update_pending_status(entry_id, "processing",
                                  proposed_route=route, proposed_layer=layer)
            total_written += 1

        if batch_idx < len(batches) - 1:
            time.sleep(SLEEP_SEC)

    if not dry_run and total_written > 0:
        write_notification(
            "pending_ready",
            f"批处理完成：{total_written} 条待审批，输入 /review 查看",
        )
        logger.info("[BatchProcessor] ✓ 完成，%d 条已写入 awaiting_approval", total_written)
    elif not dry_run:
        logger.info("[BatchProcessor] 完成，无新条目写入（可能分类结果为空）")

    return total_written


def main():
    ap = argparse.ArgumentParser(description="蓄水池批处理器")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不调 API 不落盘")
    args = ap.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
