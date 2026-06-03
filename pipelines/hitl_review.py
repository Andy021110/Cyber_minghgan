"""
hitl_review.py — 通用 HITL 审查引擎 v1.1
数字分身底座宪法审核机：AI 初筛 + 人工裁决 → 干净的宏观宪法 Markdown

用法（SOP 规则审查）:
    python3 pipelines/hitl_review.py \\
        --domain Health \\
        --input protocols/bio_optimization_baseline.md \\
        --output protocols/bio_baseline_final.md

用法（KG 节点审查）:
    python3 pipelines/hitl_review.py \\
        --domain Health \\
        --type nodes \\
        --input yuanbao_cyber_minghan_kg.json \\
        --output protocols/health_nodes_reviewed.json
"""

import json
import re
import sys
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BATCH_SIZE   = 10
MAX_RETRIES  = 3
SLEEP_BETWEEN = 1.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("hitl_review")


# ══════════════════════════════════════════════════════════════════
#  Prompt 工厂（完全解耦，无硬编码领域词）
# ══════════════════════════════════════════════════════════════════

def build_system_prompt(domain: str) -> str:
    return f"""\
你是一个 {domain} 领域宪法审核员，负责将混乱的初始规则集净化为干净的宏观防线。

【判定标准】
宏观防线（auto_pass）：
  - 覆盖一整类行为的上限或下限
  - 包含可量化阈值（数字、单位、频率）
  - 执行无需实时监督，机器可检验

微观管理（need_review）：
  - 描述单次操作步骤或具体动作
  - 依赖特定场景或实时注意力才能执行
  - 规则本身比遵守规则更费认知资源

【输出格式】
严格输出 JSON，禁止任何额外文字：
{{
  "auto_pass": ["规则原文", ...],
  "need_review": [
    {{
      "original": "规则原文",
      "issue": "问题描述（≤20字）",
      "suggestion": "宽边界改写建议（保留核心意图，消除微观操作）"
    }}
  ]
}}"""


def build_user_prompt(rules: List[str], batch_idx: int, total: int) -> str:
    numbered = "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules))
    return (
        f"以下是第 {batch_idx+1}/{total} 批规则，共 {len(rules)} 条，请逐条判定并严格按 JSON 输出：\n\n"
        f"{numbered}"
    )


# ══════════════════════════════════════════════════════════════════
#  模块 1 — RuleLoader
# ══════════════════════════════════════════════════════════════════

def load_rules(input_path: Path) -> List[str]:
    """
    自动识别输入格式并提取规则列表。

    支持：
    - .md  → 提取编号列表行 (^\d+\. ...)
    - .json → 三种结构：数组 / {"rules":[...]} / 进度文件 {"0":{"sop_rules":[...]}}
    """
    suffix = input_path.suffix.lower()
    text   = input_path.read_text(encoding="utf-8")

    if suffix == ".md":
        rules = re.findall(r"^\d+\.\s+(.+)", text, re.MULTILINE)
        logger.info("[Loader] Markdown → 提取 %d 条规则", len(rules))
        return [r.strip() for r in rules if r.strip()]

    if suffix == ".json":
        data = json.loads(text)

        # 直接数组
        if isinstance(data, list):
            rules = [str(r) for r in data if r]
            logger.info("[Loader] JSON 数组 → %d 条规则", len(rules))
            return rules

        if isinstance(data, dict):
            # {"rules": [...]}
            if "rules" in data:
                rules = [str(r) for r in data["rules"] if r]
                logger.info("[Loader] JSON rules 键 → %d 条规则", len(rules))
                return rules

            # 进度文件 {"0": {"sop_rules": [...]}, "1": {...}}
            rules = []
            for key in sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                batch = data[key]
                if isinstance(batch, dict) and "sop_rules" in batch:
                    rules.extend(batch["sop_rules"])
            if rules:
                logger.info("[Loader] 进度文件 → 展开 %d 条规则", len(rules))
                return rules

    raise ValueError(f"无法识别的输入格式：{input_path}")


# ══════════════════════════════════════════════════════════════════
#  模块 2 — 去重
# ══════════════════════════════════════════════════════════════════

def dedup_rules(rules: List[str]) -> List[str]:
    """前 12 字规范化指纹去重，保留首次出现原文。"""
    seen: set = set()
    result: List[str] = []
    for r in rules:
        key = re.sub(r"\s+", "", r).lower()[:12]
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


# ══════════════════════════════════════════════════════════════════
#  模块 3 — BatchClassifier
# ══════════════════════════════════════════════════════════════════

def _strip_fence(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    return re.sub(r"\s*```$", "", raw).strip()


def classify_batch(
    rules: List[str],
    batch_idx: int,
    total_batches: int,
    domain: str,
    client: anthropic.Anthropic,
) -> Tuple[List[str], List[Dict]]:
    """
    调用 API 对一批规则做宏观/微观分流。
    返回 (auto_pass_rules, need_review_items)。
    失败时保守降级：将整批归入 auto_pass，不丢数据。
    """
    system_prompt = build_system_prompt(domain)
    user_prompt   = build_user_prompt(rules, batch_idx, total_batches)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw    = _strip_fence(resp.content[0].text)
            result = json.loads(raw)

            auto_pass   = result.get("auto_pass", [])
            need_review = result.get("need_review", [])

            logger.info(
                "[Classifier] Batch %d/%d → auto:%d  review:%d",
                batch_idx + 1, total_batches, len(auto_pass), len(need_review),
            )
            return auto_pass, need_review

        except json.JSONDecodeError as e:
            logger.warning(
                "[Classifier] Batch %d JSON 解析失败（尝试 %d/%d）: %s",
                batch_idx + 1, attempt, MAX_RETRIES, e,
            )
        except Exception as e:
            logger.warning(
                "[Classifier] Batch %d API 错误（尝试 %d/%d）: %s",
                batch_idx + 1, attempt, MAX_RETRIES, e,
            )
            if attempt < MAX_RETRIES:
                time.sleep(4 * attempt)

    logger.error("[Classifier] Batch %d 全部重试失败，整批保守放行", batch_idx + 1)
    return rules, []


# ══════════════════════════════════════════════════════════════════
#  模块 4 — HITL Terminal
# ══════════════════════════════════════════════════════════════════

_W = 58  # 终端宽度

def _bar(char: str = "─") -> str:
    return char * _W

def _wrap(text: str, width: int = 52, indent: str = "    ") -> None:
    for i in range(0, max(len(text), 1), width):
        print(f"{indent}{text[i:i+width]}")


def generate_revision_proposal(
    original: str,
    user_comment: str,
    domain: str,
    client: anthropic.Anthropic,
) -> Dict:
    """
    根据用户的自然语言表态，AI 决定删除或改写规则。
    返回 {"action": "delete"} 或 {"action": "rewrite", "result": "改写后规则"}。
    """
    system = (
        f"你是 {domain} 领域宪法编辑。根据用户对规则的看法，"
        f"决定该规则应被删除还是改写为更合适的宏观防线。\n"
        f"输出严格 JSON，不附任何说明：\n"
        f'  {{"action": "delete"}}  或\n'
        f'  {{"action": "rewrite", "result": "改写后规则（保留核心意图，消除微观操作）"}}'
    )
    user_msg = f"原始规则：{original}\n\n用户的看法：{user_comment}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = _strip_fence(resp.content[0].text)
            return json.loads(raw)
        except Exception as e:
            logger.warning("[Revision] 生成方案失败（尝试 %d/%d）: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(3)

    # 降级：保留原规则
    return {"action": "rewrite", "result": original}


def hitl_review_item(
    item: Dict,
    idx: int,
    total: int,
    domain: str,
    client: anthropic.Anthropic,
) -> Tuple:
    """
    一次裁决 UI。返回：
      ("decided", rule_str)       — [1] 或 [2] 直接定稿
      ("pending_revision", entry) — [3] 进入二次审核池
    """
    original   = item.get("original", "")
    issue      = item.get("issue", "")
    suggestion = item.get("suggestion", "")

    print(f"\n{'═' * _W}")
    print(f"  ⚠  需要人工裁决  ({idx} / {total})")
    print(_bar())
    print("  原始规则:")
    _wrap(original)
    print()
    print(f"  AI 问题诊断:  {issue}")
    print("  AI 修改建议:")
    _wrap(suggestion)
    print(_bar())
    print("    [1] 采纳 AI 建议    [2] 保留原始规则    [3] 发表看法（AI 辅助）")

    while True:
        try:
            choice = input("  > 你的选择: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  检测到中断，默认保留原始规则。")
            return ("decided", original)

        if choice == "1":
            print("  ✓ 已采纳 AI 建议\n")
            return ("decided", suggestion)

        elif choice == "2":
            print("  ✓ 已保留原始规则\n")
            return ("decided", original)

        elif choice == "3":
            try:
                comment = input("  说说你的看法（可以说「删了」或描述你的想法）: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  中断，使用原始规则。")
                return ("decided", original)

            if not comment:
                print("  输入为空，请重试。")
                continue

            print("  AI 正在理解你的意图...")
            proposal = generate_revision_proposal(original, comment, domain, client)
            entry = {
                "original":     original,
                "user_comment": comment,
                "ai_proposal":  proposal,
            }
            action_desc = "删除该规则" if proposal.get("action") == "delete" else f"改写为：{proposal.get('result', '')}"
            print(f"  AI 方案：{action_desc}")
            print("  ✓ 已加入二次审核池，稍后确认\n")
            return ("pending_revision", entry)

        else:
            print("  请输入 1、2 或 3。")


def hitl_revision_review(entry: Dict, idx: int, total: int, domain: str, client: anthropic.Anthropic) -> Optional[str]:
    """
    二次审核 UI。返回：
      str  — 最终规则（采纳改写结果 或 回退原文）
      None — 删除该条（action=delete 且用户确认）
    """
    original  = entry["original"]
    comment   = entry["user_comment"]
    proposal  = entry["ai_proposal"]
    action    = proposal.get("action", "rewrite")
    result    = proposal.get("result", original)

    while True:
        print(f"\n{'═' * _W}")
        print(f"  ✎  二次审核  ({idx} / {total})")
        print(_bar())
        print("  原始规则:")
        _wrap(original)
        print(f"\n  你的看法:  {comment}")
        print()
        if action == "delete":
            print("  AI 方案:  【删除该条规则】")
        else:
            print("  AI 方案（改写后）:")
            _wrap(result)
        print(_bar())
        print("    [A] 确认采纳    [B] 放弃，回退原规则    [C] 重新表达看法")

        try:
            choice = input("  > 你的选择: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n  中断，回退原规则。")
            return original

        if choice == "A":
            if action == "delete":
                print("  ✓ 已删除该条规则\n")
                return None
            else:
                print("  ✓ 已采纳改写方案\n")
                return result

        elif choice == "B":
            print("  ✓ 已回退至原始规则\n")
            return original

        elif choice == "C":
            try:
                comment = input("  重新说说你的看法: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  中断，回退原规则。")
                return original
            if not comment:
                print("  输入为空，请重试。")
                continue
            print("  AI 重新理解中...")
            proposal = generate_revision_proposal(original, comment, domain, client)
            entry["user_comment"] = comment
            entry["ai_proposal"]  = proposal
            action = proposal.get("action", "rewrite")
            result = proposal.get("result", original)

        else:
            print("  请输入 A、B 或 C。")


# ══════════════════════════════════════════════════════════════════
#  模块 5 — Markdown 输出
# ══════════════════════════════════════════════════════════════════

def write_markdown(
    rules: List[str],
    domain: str,
    output_path: Path,
    source_name: str,
    raw_count: int,
    auto_count: int,
    review_count: int,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {domain} 优化基线协议",
        "",
        f"> HITL 审查生成 · {now}  ",
        f"> 来源: `{source_name}`  ",
        f"> 原始规则 {raw_count} 条 → AI 自动放行 {auto_count}，人工裁决 {review_count}，去重后 **{len(rules)} 条**",
        "",
        "---",
        "",
        "## 宏观防线",
        "",
    ]
    for i, rule in enumerate(rules, 1):
        lines.append(f"{i}. {rule}")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("[Writer] 已写入：%s（%d 条）", output_path, len(rules))


# ══════════════════════════════════════════════════════════════════
#  模块 6 — Checkpoint（断点续审）
# ══════════════════════════════════════════════════════════════════

def _ckpt_path(output_path: Path) -> Path:
    return output_path.with_suffix(".hitl_checkpoint.json")


def _load_ckpt(output_path: Path) -> Optional[Dict]:
    p = _ckpt_path(output_path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _save_ckpt(output_path: Path, ckpt: Dict) -> None:
    p = _ckpt_path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(ckpt, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _delete_ckpt(output_path: Path) -> None:
    p = _ckpt_path(output_path)
    if p.exists():
        p.unlink()


# ══════════════════════════════════════════════════════════════════
#  模块 7 — Orchestrator
# ══════════════════════════════════════════════════════════════════

class Orchestrator:
    def __init__(self, domain: str, auto_mode: bool = False, limit: Optional[int] = None):
        self.domain    = domain
        self.auto_mode = auto_mode
        self.limit     = limit
        self.client    = anthropic.Anthropic()

    def run(self, input_path: Path, output_path: Path) -> None:
        ckpt = _load_ckpt(output_path)

        if ckpt:
            logger.info(
                "[Orchestrator] 加载 checkpoint：已裁决 %d 条，待裁决 %d 条，待二次审核 %d 条",
                len(ckpt["decided"]), len(ckpt["pending"]), len(ckpt.get("pending_revision", [])),
            )
            auto_pass        = ckpt["auto_pass"]
            pending          = ckpt["pending"]
            decided          = ckpt["decided"]
            pending_revision = ckpt.get("pending_revision", [])
            raw_count        = ckpt["raw_count"]
        else:
            # ── Phase 1：批次分类（首次运行）────────────────────────
            raw_rules = load_rules(input_path)
            rules     = dedup_rules(raw_rules)
            raw_count = len(raw_rules)
            logger.info("[Orchestrator] 去重后：%d 条（原 %d 条）", len(rules), raw_count)

            batches       = [rules[i:i+BATCH_SIZE] for i in range(0, len(rules), BATCH_SIZE)]
            total_batches = len(batches)
            auto_pass: List[str]  = []
            pending:   List[Dict] = []

            for idx, batch in enumerate(batches):
                auto, review = classify_batch(
                    batch, idx, total_batches, self.domain, self.client
                )
                auto_pass.extend(auto)
                pending.extend(review)
                if idx < total_batches - 1:
                    time.sleep(SLEEP_BETWEEN)

            logger.info(
                "[Orchestrator] 分类完成：auto_pass %d 条，need_review %d 条",
                len(auto_pass), len(pending),
            )
            decided: List[str] = []
            pending_revision: List[Dict] = []
            ckpt = {
                "domain":           self.domain,
                "source":           input_path.name,
                "raw_count":        raw_count,
                "auto_pass":        auto_pass,
                "pending":          pending,
                "decided":          decided,
                "pending_revision": pending_revision,
            }
            _save_ckpt(output_path, ckpt)

        total_review = len(pending) + len(decided) + len(pending_revision)

        # ── Phase 2：HITL 一次裁决 ───────────────────────────────
        if self.auto_mode:
            logger.info("[Orchestrator] --auto 模式：全部采纳 AI 建议")
            decided += [item.get("suggestion", item.get("original", "")) for item in pending]
            pending.clear()
        elif pending:
            todo      = pending[:self.limit] if self.limit else pending
            remaining = pending[self.limit:] if self.limit else []
            done_so_far = len(decided) + len(pending_revision)

            print(f"\n{'═'*_W}")
            print(f"  本次裁决 {len(todo)} 条（已完成 {done_so_far}/{total_review}）")
            if remaining:
                print(f"  还剩 {len(remaining)} 条留待下次")
            print(f"{'═'*_W}")

            for item in todo:
                global_idx = done_so_far + 1
                action, value = hitl_review_item(
                    item, global_idx, total_review, self.domain, self.client
                )
                if action == "decided":
                    decided.append(value)
                else:
                    pending_revision.append(value)
                done_so_far += 1
                ckpt["pending"]          = remaining
                ckpt["decided"]          = decided
                ckpt["pending_revision"] = pending_revision
                _save_ckpt(output_path, ckpt)

            pending = remaining

        # ── Phase 3：二次审核（pending_revision 池）──────────────
        if pending_revision and not pending:
            print(f"\n{'═'*_W}")
            print(f"  进入二次审核：共 {len(pending_revision)} 条待确认")
            print(f"{'═'*_W}")

            final_revision: List[Dict] = []
            for i, entry in enumerate(pending_revision, 1):
                result = hitl_revision_review(
                    entry, i, len(pending_revision), self.domain, self.client
                )
                if result is not None:
                    decided.append(result)
                # None = 删除，不加入 decided

            pending_revision.clear()
            ckpt["decided"]          = decided
            ckpt["pending_revision"] = []
            _save_ckpt(output_path, ckpt)
        else:
            print("\n  所有规则均已裁决完毕。")

        # ── 还有待裁决或待二次审核的条目 → 提示下次继续 ────────────
        if pending or pending_revision:
            if pending:
                print(f"\n  本次完成。还剩 {len(pending)} 条待裁决。")
            if pending_revision:
                print(f"  还有 {len(pending_revision)} 条在二次审核池（裁决完所有条目后自动进入）。")
            print(f"  再次运行相同命令即可继续。\n")
            return

        # ── 全部裁决完毕 → 合并输出 ──────────────────────────────
        final_rules = dedup_rules(auto_pass + decided)

        print(f"\n{'═'*_W}")
        print(f"  全部审查完成：{len(auto_pass)} 条自动放行，{total_review} 条人工裁决")
        print(f"  去重后最终规则数：{len(final_rules)} 条")
        print(f"{'═'*_W}\n")

        write_markdown(
            final_rules,
            self.domain,
            output_path,
            ckpt["source"],
            raw_count,
            len(auto_pass),
            total_review,
        )
        _delete_ckpt(output_path)
        print(f"  输出文件：{output_path}")
        print("  ✓ 宪法审查完成\n")


# ══════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════

# ── KG 节点专用模块 ───────────────────────────────────────────────

def build_node_system_prompt(domain: str) -> str:
    return f"""\
你是 {domain} 领域的因果节点审核员。
每条节点描述一个「触发事件 → 生理/心理反应」的因果关系。

判定标准：
  auto_pass   — 因果链准确、有实际意义、不与其他节点明显重复
  need_review — 因果关系牵强、描述模糊、与其他节点高度重叠、或反应描述不够具体

输出严格 JSON，禁止附加任何说明文字：
{{
  "auto_pass":   [{{"node_id":"...","trigger":"...","reaction":"..."}}],
  "need_review": [{{"node_id":"...","trigger":"...","reaction":"...","issue":"问题(≤20字)"}}]
}}"""


def load_kg_nodes(kg_path: Path, domain: str) -> List[Dict]:
    """从 KG JSON 提取指定 domain 的 kg_nodes。"""
    kg = json.loads(kg_path.read_text(encoding="utf-8"))
    nodes = (kg["nodes"]["Cyber_Minghan"]
               .get("domains", {})
               .get(domain, {})
               .get("kg_nodes", []))
    logger.info("[NodeLoader] %s.kg_nodes: %d 条", domain, len(nodes))
    return nodes


def classify_nodes_batch(
    nodes: List[Dict],
    batch_idx: int,
    total_batches: int,
    domain: str,
    client: anthropic.Anthropic,
) -> Tuple[List[Dict], List[Dict]]:
    """对一批 KG 节点做 auto_pass / need_review 分流。"""
    system_prompt = build_node_system_prompt(domain)
    items_text = json.dumps(
        [{"node_id": n.get("node_id",""), "trigger": n.get("trigger",""), "reaction": n.get("reaction","")}
         for n in nodes],
        ensure_ascii=False, indent=2
    )
    user_msg = (
        f"以下是第 {batch_idx+1}/{total_batches} 批节点，共 {len(nodes)} 条，请逐条判定：\n\n"
        f"{items_text}"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw    = _strip_fence(resp.content[0].text)
            result = json.loads(raw)
            auto   = result.get("auto_pass", [])
            review = result.get("need_review", [])
            logger.info("[NodeClassifier] Batch %d/%d → auto:%d review:%d",
                        batch_idx+1, total_batches, len(auto), len(review))
            return auto, review
        except Exception as e:
            logger.warning("[NodeClassifier] Batch %d 失败（尝试 %d/%d）: %s",
                           batch_idx+1, attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(4 * attempt)

    logger.error("[NodeClassifier] Batch %d 全部重试失败，整批保守放行", batch_idx+1)
    return nodes, []


def hitl_node_item(node: Dict, idx: int, total: int, domain: str, client: anthropic.Anthropic) -> Tuple:
    """
    KG 节点单条裁决 UI。
    返回 ("decided", node_dict) 或 ("pending_revision", entry)。
    """
    issue    = node.get("issue", "")
    trigger  = node.get("trigger", "")
    reaction = node.get("reaction", "")

    print(f"\n{'═'*_W}")
    print(f"  ⚠  节点裁决  ({idx} / {total})")
    print(_bar())
    print("  触发事件:")
    _wrap(trigger)
    print("  生理/心理反应:")
    _wrap(reaction)
    if issue:
        print(f"\n  AI 问题:  {issue}")
    print(_bar())
    print("    [1] 保留该节点    [2] 删除该节点    [3] 发表看法（AI 辅助）")

    while True:
        try:
            choice = input("  > 你的选择: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  中断，默认保留。")
            return ("decided", node)

        if choice == "1":
            print("  ✓ 已保留\n")
            return ("decided", node)
        elif choice == "2":
            print("  ✓ 已删除\n")
            return ("decided", None)
        elif choice == "3":
            try:
                comment = input("  说说你的看法: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  中断，默认保留。")
                return ("decided", node)
            if not comment:
                print("  输入为空，请重试。")
                continue
            print("  AI 处理中...")
            proposal = generate_revision_proposal(
                f"trigger: {trigger}\nreaction: {reaction}", comment, domain, client
            )
            entry = {"original": node, "user_comment": comment, "ai_proposal": proposal}
            print(f"  AI 方案：{'删除' if proposal.get('action')=='delete' else proposal.get('result','')}")
            print("  ✓ 已加入二次审核池\n")
            return ("pending_revision", entry)
        else:
            print("  请输入 1、2 或 3。")


def hitl_node_revision(entry: Dict, idx: int, total: int, domain: str, client: anthropic.Anthropic) -> Optional[Dict]:
    """KG 节点二次审核。返回最终节点 dict 或 None（删除）。"""
    original = entry["original"]
    comment  = entry["user_comment"]
    proposal = entry["ai_proposal"]
    action   = proposal.get("action", "rewrite")
    result   = proposal.get("result", "")

    while True:
        print(f"\n{'═'*_W}")
        print(f"  ✎  节点二次审核  ({idx} / {total})")
        print(_bar())
        print(f"  触发: {original.get('trigger','')[:50]}")
        print(f"  反应: {original.get('reaction','')[:50]}")
        print(f"\n  你的看法: {comment}")
        if action == "delete":
            print("  AI 方案: 【删除该节点】")
        else:
            print(f"  AI 方案: {result[:80]}")
        print(_bar())
        print("    [A] 确认    [B] 回退保留原节点    [C] 重新表达")

        try:
            choice = input("  > 你的选择: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            return original

        if choice == "A":
            if action == "delete":
                print("  ✓ 已删除\n")
                return None
            node = dict(original)
            node["reaction"] = result
            print("  ✓ 已采纳改写\n")
            return node
        elif choice == "B":
            print("  ✓ 已保留原节点\n")
            return original
        elif choice == "C":
            try:
                comment = input("  重新说说: ").strip()
            except (EOFError, KeyboardInterrupt):
                return original
            if not comment:
                continue
            proposal = generate_revision_proposal(
                f"trigger: {original.get('trigger','')}\nreaction: {original.get('reaction','')}",
                comment, domain, client
            )
            entry["user_comment"] = comment
            entry["ai_proposal"]  = proposal
            action = proposal.get("action", "rewrite")
            result = proposal.get("result", "")
        else:
            print("  请输入 A、B 或 C。")


class NodeOrchestrator:
    """KG 节点专用审查流水线。"""

    def __init__(self, domain: str, auto_mode: bool = False, limit: Optional[int] = None):
        self.domain    = domain
        self.auto_mode = auto_mode
        self.limit     = limit
        self.client    = anthropic.Anthropic()

    def run(self, kg_path: Path, output_path: Path) -> None:
        ckpt = _load_ckpt(output_path)

        if ckpt:
            logger.info("[NodeOrchestrator] 加载 checkpoint：已裁决 %d，待裁决 %d，待二次审核 %d",
                        len(ckpt["decided"]), len(ckpt["pending"]), len(ckpt.get("pending_revision", [])))
            auto_pass        = ckpt["auto_pass"]
            pending          = ckpt["pending"]
            decided          = ckpt["decided"]
            pending_revision = ckpt.get("pending_revision", [])
            raw_count        = ckpt["raw_count"]
        else:
            raw_nodes = load_kg_nodes(kg_path, self.domain)
            raw_count = len(raw_nodes)
            batches   = [raw_nodes[i:i+BATCH_SIZE] for i in range(0, raw_count, BATCH_SIZE)]
            auto_pass, pending = [], []

            for idx, batch in enumerate(batches):
                a, r = classify_nodes_batch(batch, idx, len(batches), self.domain, self.client)
                auto_pass.extend(a)
                pending.extend(r)
                if idx < len(batches) - 1:
                    time.sleep(SLEEP_BETWEEN)

            logger.info("[NodeOrchestrator] 分类完成：auto:%d review:%d", len(auto_pass), len(pending))
            decided, pending_revision = [], []
            ckpt = {"domain": self.domain, "raw_count": raw_count,
                    "auto_pass": auto_pass, "pending": pending,
                    "decided": decided, "pending_revision": pending_revision}
            _save_ckpt(output_path, ckpt)

        total_review = len(pending) + len(decided) + len(pending_revision)

        # Phase 2: 一次裁决
        if self.auto_mode:
            decided += [n for n in pending]
            pending.clear()
        elif pending:
            todo      = pending[:self.limit] if self.limit else pending
            remaining = pending[self.limit:] if self.limit else []
            done_so_far = len(decided) + len(pending_revision)

            print(f"\n{'═'*_W}")
            print(f"  本次裁决 {len(todo)} 条节点（已完成 {done_so_far}/{total_review}）")
            if remaining:
                print(f"  还剩 {len(remaining)} 条留待下次")
            print(f"{'═'*_W}")

            for item in todo:
                action, value = hitl_node_item(item, done_so_far+1, total_review, self.domain, self.client)
                if action == "decided":
                    decided.append(value)
                else:
                    pending_revision.append(value)
                done_so_far += 1
                ckpt["pending"] = remaining
                ckpt["decided"] = decided
                ckpt["pending_revision"] = pending_revision
                _save_ckpt(output_path, ckpt)
            pending = remaining

        # Phase 3: 二次审核
        if pending_revision and not pending:
            print(f"\n{'═'*_W}")
            print(f"  进入二次审核：{len(pending_revision)} 条待确认")
            print(f"{'═'*_W}")
            for i, entry in enumerate(pending_revision, 1):
                result = hitl_node_revision(entry, i, len(pending_revision), self.domain, self.client)
                if result is not None:
                    decided.append(result)
            pending_revision.clear()
            ckpt["decided"] = decided
            ckpt["pending_revision"] = []
            _save_ckpt(output_path, ckpt)

        if pending or pending_revision:
            print(f"\n  还剩 {len(pending)} 条待裁决，再次运行相同命令继续。\n")
            return

        # 全部完成 → 写出审查后节点 JSON（过滤掉 None）
        final_nodes = [n for n in auto_pass + decided if n is not None]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(final_nodes, ensure_ascii=False, indent=2), encoding="utf-8")
        _delete_ckpt(output_path)

        print(f"\n{'═'*_W}")
        print(f"  节点审查完成：保留 {len(final_nodes)} 条（原 {raw_count} 条）")
        print(f"  输出文件：{output_path}")
        print(f"{'═'*_W}\n")



def main():
    ap = argparse.ArgumentParser(
        description="HITL 审查引擎 — 通用宪法审核机",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--domain", required=True,
                    help="领域名称，如 Health / Finance / Work")
    ap.add_argument("--input",  required=True, type=Path,
                    help="输入文件（.md 编号列表 或 .json 规则/KG文件）")
    ap.add_argument("--output", required=True, type=Path,
                    help="输出文件路径（rules模式→.md，nodes模式→.json）")
    ap.add_argument("--type",   choices=["rules", "nodes"], default="rules",
                    help="审查类型：rules=SOP规则（默认），nodes=KG因果节点")
    ap.add_argument("--auto",   action="store_true",
                    help="CI 模式：跳过 HITL，全部采纳 AI 建议")
    ap.add_argument("--limit",  type=int, default=None,
                    help="本次最多裁决 N 条，剩余下次继续（断点续审）")
    args = ap.parse_args()

    if not args.input.exists():
        ap.error(f"输入文件不存在：{args.input}")

    if args.type == "nodes":
        NodeOrchestrator(
            domain=args.domain,
            auto_mode=args.auto,
            limit=args.limit,
        ).run(args.input, args.output)
    else:
        Orchestrator(
            domain=args.domain,
            auto_mode=args.auto,
            limit=args.limit,
        ).run(args.input, args.output)


if __name__ == "__main__":
    main()
