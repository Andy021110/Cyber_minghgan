"""
evals/retrieval_ab.py — 检索质量 A/B 对比（keyword vs 混合检索）

为什么只测检索不测生成：
完整 LongMemEval 跑分需要 LLM-as-judge（有钱有成见的风险），而「记忆 Agent」的核心差异
在检索层——生成层大家都用同一个模型。因此这里只测 **检索召回**：
给定问题，top-k 里有没有命中 gold 会话。这个指标零 API 调用、可复现、可进 CI。

指标：
- Recall@k = |命中 ∩ gold| / |gold|（单 gold 时等价于 Hit@k）
- MRR@k    = 1 / 首个命中的排名（未命中记 0）

用法：
    python3 evals/retrieval_ab.py --data evals/公认评测集/LongMemEval/longmemeval_oracle.json --k 5 --limit 50
    CYBER_EMBEDDING_PROVIDER=bge python3 evals/retrieval_ab.py --data ... --k 5   # 启用本地 BGE 对比

注意：数据集不入库（体积/许可），缺失时会明确报错而不是静默返回 0 分。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from memory.embeddings import EmbeddingProvider, ZeroEmbeddingProvider, get_provider  # noqa: E402
from memory.episodic_store import EpisodicStore  # noqa: E402


def recall_at_k(retrieved: list[str], gold: set[str], k: int = 5) -> float:
    """Recall@k：命中 gold 的比例。gold 为空时返回 0（不应静默算满分）。"""
    if not gold:
        return 0.0
    top = set(retrieved[:k])
    return len(top & gold) / len(gold)


def mrr_at_k(retrieved: list[str], gold: set[str], k: int = 5) -> float:
    """MRR@k：首个命中结果的排名倒数。"""
    for i, rid in enumerate(retrieved[:k], start=1):
        if rid in gold:
            return 1.0 / i
    return 0.0


def ingest_item(epi: EpisodicStore, item: dict) -> dict[str, str]:
    """把一个 LongMemEval 题目的 haystack 会话灌进 EpisodicStore。

    返回 eid -> session_id 的映射，用于把检索结果还原成会话级命中。
    """
    epi.clear()
    eid2sid: dict[str, str] = {}
    sessions = item.get("haystack_sessions") or []
    dates = item.get("haystack_dates") or []
    ids = item.get("haystack_session_ids") or []

    for si, sess in enumerate(sessions):
        ts = dates[si] if si < len(dates) else f"session-{si}"
        sid = str(ids[si]) if si < len(ids) else f"session-{si}"
        buf_user: list[str] = []
        buf_asst: list[str] = []
        for turn in sess or []:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role == "user":
                if buf_user and buf_asst:
                    ep = epi.append(
                        ts=str(ts)[:32],
                        user_text="\n".join(buf_user),
                        assistant_text="\n".join(buf_asst),
                        source="LongMemEval",
                    )
                    eid2sid[ep.eid] = sid
                    buf_user, buf_asst = [], []
                buf_user.append(content)
            elif role == "assistant":
                buf_asst.append(content)
        if buf_user or buf_asst:
            ep = epi.append(
                ts=str(ts)[:32],
                user_text="\n".join(buf_user),
                assistant_text="\n".join(buf_asst),
                source="LongMemEval",
            )
            eid2sid[ep.eid] = sid
    return eid2sid


def evaluate_arm(
    items: list[dict],
    provider: EmbeddingProvider | None,
    k: int = 5,
    alpha: float = 0.4,
    limit: int | None = None,
) -> dict:
    """跑一个检索臂（keyword-only 或 hybrid），返回聚合指标。"""
    provider = provider or ZeroEmbeddingProvider()
    subset = items[:limit] if limit else items

    per_type: dict[str, list[float]] = defaultdict(list)
    mrr_all: list[float] = []
    details: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="retrieval_ab_") as tmp:
        epi = EpisodicStore(Path(tmp) / "epi.jsonl", provider=provider, vector_alpha=alpha)
        for item in subset:
            eid2sid = ingest_item(epi, item)
            question = item.get("question", "")
            gold = {str(x) for x in (item.get("answer_session_ids") or [])}
            hits = epi.search(question, limit=max(k, 10))
            retrieved = [eid2sid.get(h.get("eid", ""), "") for h in hits]
            retrieved = [r for r in retrieved if r]

            r = recall_at_k(retrieved, gold, k)
            m = mrr_at_k(retrieved, gold, k)
            qtype = str(item.get("question_type", "unknown"))
            per_type[qtype].append(r)
            mrr_all.append(m)
            details.append(
                {
                    "question_id": item.get("question_id", ""),
                    "question_type": qtype,
                    "recall": r,
                    "mrr": m,
                }
            )

    n = max(1, len(subset))
    return {
        "k": k,
        "alpha": alpha,
        "n": len(subset),
        "recall_at_k": round(sum(d["recall"] for d in details) / n, 4),
        "mrr_at_k": round(sum(mrr_all) / n, 4),
        "by_type": {
            t: round(sum(v) / len(v), 4) for t, v in sorted(per_type.items())
        },
        "details": details,
    }


def run_ab(
    items: list[dict],
    k: int = 5,
    alpha: float = 0.4,
    limit: int | None = None,
    hybrid_provider: EmbeddingProvider | None = None,
) -> dict:
    """对照组（纯关键词） vs 实验组（混合检索）。"""
    baseline = evaluate_arm(items, ZeroEmbeddingProvider(), k=k, alpha=0.0, limit=limit)
    hybrid = evaluate_arm(
        items, hybrid_provider or get_provider(), k=k, alpha=alpha, limit=limit
    )
    return {
        "baseline_keyword_only": baseline,
        "hybrid": hybrid,
        "delta_recall": round(hybrid["recall_at_k"] - baseline["recall_at_k"], 4),
    }


def load_items(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"数据集缺失：{p}\n"
            "本仓库不收录数据集，下载方式见 evals/数据集来源与下载说明.md"
        )
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("data", [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检索质量 A/B（keyword vs hybrid）")
    parser.add_argument("--data", required=True, help="longmemeval_oracle.json 路径")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--alpha", type=float, default=0.4)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="输出完整 JSON")
    args = parser.parse_args(argv)

    try:
        items = load_items(args.data)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    result = run_ab(items, k=args.k, alpha=args.alpha, limit=args.limit)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    b, h = result["baseline_keyword_only"], result["hybrid"]
    print(f"题目数 {b['n']} · k={b['k']}")
    print(f"  纯关键词  Recall@{b['k']} = {b['recall_at_k']}  MRR = {b['mrr_at_k']}")
    print(f"  混合检索  Recall@{h['k']} = {h['recall_at_k']}  MRR = {h['mrr_at_k']}"
          f"  (alpha={h['alpha']})")
    print(f"  召回提升  Δ = {result['delta_recall']}")
    if h["by_type"]:
        print("  分类型 Recall（混合）：")
        for t, v in h["by_type"].items():
            print(f"      {t}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
