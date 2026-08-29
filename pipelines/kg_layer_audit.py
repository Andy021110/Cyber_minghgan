"""
pipelines/kg_layer_audit.py — 三层动力学结构的实证审计

为什么需要这个脚本：
Id / Ego / Superego 这三层来自弗洛伊德的结构模型，它是**借来的建模坐标系**，
不是从原理推导出来的，也没有数学证明。既然不能证明它"正确"，
就只能验证它"有用"——有用的判据是可测量的：

1. 分布：三层是否都在被使用，还是事实上一堆在某一层
2. 可分性：只看节点文本，能否预测它属于哪一层？
   用字符 n-gram 朴素贝叶斯 + k 折交叉验证，对比「多数类基线」。
   **显著高于基线 = 这层划分确实编码了可区分的语义信息；
   接近基线 = 这层是装饰性的，三层和扁平单层没区别。**
3. 参数诚实性：报告样本量，样本小则结果噪声大，不能过度解读。

用法：
    python3 pipelines/kg_layer_audit.py
    python3 pipelines/kg_layer_audit.py --kg <path> --folds 5
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from cyber_planner import KG_PATH, CyberBrainStore  # noqa: E402

LAYERS = ("Id", "Superego", "Ego")


def node_text(node: dict) -> str:
    return f"{node.get('event_label', '')} {node.get('description', '')}"


# 层名泄漏：节点的动力学描述里常常直接写着「Id层」「超我」「Ego」，
# 分类器只要认出层名就能预测，等于在作弊。做可分性检验时必须先抹掉这些词。
LAYER_TOKENS = (
    "superego", "ego", "id",
    "超我", "自我", "本我",
)


def scrub_layer_tokens(text: str) -> str:
    """抹掉层名及其大小写变体，消除标签泄漏。"""
    out = text
    for tok in LAYER_TOKENS:
        for variant in {tok, tok.upper(), tok.lower(), tok.capitalize()}:
            out = out.replace(variant, "")
    return out


def node_text_clean(node: dict) -> str:
    """可分性检验专用：抹掉层名后的文本。"""
    return scrub_layer_tokens(node_text(node))


def ngrams(text: str, n: int = 3) -> list[str]:
    """字符 n-gram（中文无空格，字符级特征比词级更稳）。"""
    cleaned = "".join(ch for ch in text if not ch.isspace())
    if len(cleaned) < n:
        return [cleaned] if cleaned else []
    return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]


class MultinomialNB:
    """极简多项朴素贝叶斯（自实现，避免引入 sklearn 依赖）。"""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.classes: list[str] = []
        self.log_prior: dict[str, float] = {}
        self.log_lik: dict[str, dict[str, float]] = {}
        self.default_lik: dict[str, float] = {}
        self.vocab_size = 0

    def fit(self, docs: list[list[str]], labels: list[str]) -> None:
        self.classes = sorted(set(labels))
        counts: dict[str, Counter] = {c: Counter() for c in self.classes}
        class_doc_count: Counter = Counter(labels)
        for doc, label in zip(docs, labels):
            counts[label].update(doc)

        vocab = set()
        for c in self.classes:
            vocab.update(counts[c].keys())
        self.vocab_size = max(1, len(vocab))

        total_docs = max(1, len(labels))
        for c in self.classes:
            self.log_prior[c] = math.log(class_doc_count[c] / total_docs)
            total_terms = sum(counts[c].values())
            denom = total_terms + self.alpha * self.vocab_size
            self.log_lik[c] = {
                term: math.log((cnt + self.alpha) / denom)
                for term, cnt in counts[c].items()
            }
            self.default_lik[c] = math.log(self.alpha / denom)

    def predict(self, doc: list[str]) -> str:
        best, best_score = None, -float("inf")
        for c in self.classes:
            score = self.log_prior[c]
            for term in doc:
                score += self.log_lik[c].get(term, self.default_lik[c])
            if score > best_score:
                best, best_score = c, score
        return best or self.classes[0]


def cross_val_accuracy(
    docs: list[list[str]], labels: list[str], folds: int = 5, seed: int = 42
) -> tuple[float, float, dict]:
    """k 折交叉验证；同时返回多数类基线。"""
    idx = list(range(len(labels)))
    random.Random(seed).shuffle(idx)
    buckets: list[list[int]] = [[] for _ in range(folds)]
    for i, pos in enumerate(idx):
        buckets[i % folds].append(pos)

    correct = 0
    confusion: dict[str, dict[str, int]] = {
        c: {c2: 0 for c2 in LAYERS} for c in LAYERS
    }
    for f in range(folds):
        test_idx = set(buckets[f])
        train_idx = [i for i in idx if i not in test_idx]
        if not train_idx:
            continue
        clf = MultinomialNB()
        clf.fit([docs[i] for i in train_idx], [labels[i] for i in train_idx])
        for i in buckets[f]:
            pred = clf.predict(docs[i])
            if pred == labels[i]:
                correct += 1
            confusion[labels[i]][pred] += 1

    accuracy = correct / max(1, len(labels))
    majority = Counter(labels).most_common(1)[0][1] / max(1, len(labels))
    return accuracy, majority, confusion


def distinctive_terms(nodes_by_layer: dict[str, list[dict]], top_k: int = 8) -> dict:
    """每层的代表性 3-gram（按层内频率 / 全局频率 排序）。"""
    per_layer: dict[str, Counter] = {}
    glob: Counter = Counter()
    for layer, nodes in nodes_by_layer.items():
        c: Counter = Counter()
        for n in nodes:
            grams = ngrams(node_text_clean(n))  # 同样抹掉层名，否则特征里全是标签
            c.update(grams)
            glob.update(grams)
        per_layer[layer] = c

    total_by_layer = {l: max(1, sum(c.values())) for l, c in per_layer.items()}
    glob_total = max(1, sum(glob.values()))
    out = {}
    for layer, c in per_layer.items():
        scored = []
        for term, cnt in c.items():
            if cnt < 3:
                continue
            p_in = cnt / total_by_layer[layer]
            p_all = glob[term] / glob_total
            scored.append((p_in / (p_all + 1e-9), term, cnt))
        scored.sort(reverse=True)
        out[layer] = [{"term": t, "lift": round(s, 2), "count": n} for s, t, n in scored[:top_k]]
    return out


def audit(kg_path: Path, folds: int = 5) -> dict:
    store = CyberBrainStore(kg_path=kg_path)
    nodes_by_layer: dict[str, list[dict]] = defaultdict(list)
    for lst in store._node_lists():
        for node in lst:
            layer = node.get("layer", "?")
            nodes_by_layer[layer].append(node)

    docs_raw, docs_clean, labels = [], [], []
    for layer, nodes in nodes_by_layer.items():
        for n in nodes:
            docs_raw.append(ngrams(node_text(n)))
            docs_clean.append(ngrams(node_text_clean(n)))
            labels.append(layer)

    n_total = len(labels)
    distribution = {}
    for layer in LAYERS:
        ns = nodes_by_layer.get(layer, [])
        imps = [float(n.get("importance", 0) or 0) for n in ns]
        distribution[layer] = {
            "count": len(ns),
            "share": round(len(ns) / max(1, n_total), 3),
            "avg_importance": round(sum(imps) / len(imps), 2) if imps else 0.0,
        }

    # raw：含层名（有泄漏，会高估）；clean：抹掉层名（诚实值）
    acc_raw, majority, confusion = cross_val_accuracy(docs_raw, labels, folds=folds)
    acc_clean, _, _ = cross_val_accuracy(docs_clean, labels, folds=folds)

    return {
        "total_nodes": n_total,
        "distribution": distribution,
        "separability_raw": {
            "cv_accuracy": round(acc_raw, 3),
            "majority_baseline": round(majority, 3),
            "lift_over_baseline": round(acc_raw - majority, 3),
            "note": "含层名泄漏，仅作对照，不可引用",
        },
        "separability": {
            "cv_accuracy": round(acc_clean, 3),
            "majority_baseline": round(majority, 3),
            "lift_over_baseline": round(acc_clean - majority, 3),
            "folds": folds,
            "note": "已抹掉层名（Id/Ego/Superego/本我/自我/超我）后的诚实值",
        },
        "confusion": confusion,
        "distinctive_terms": distinctive_terms(nodes_by_layer),
        "caveat": (
            f"样本仅 {n_total} 个节点，k 折 CV 方差较大；"
            "本结果只能作为粗判据，不能当作显著性证据。"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="三层动力学结构实证审计")
    ap.add_argument("--kg", default=str(KG_PATH))
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = audit(Path(args.kg), folds=args.folds)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"节点总数：{report['total_nodes']}")
    print("\n[1] 层分布")
    for layer, d in report["distribution"].items():
        print(f"  {layer:<10} {d['count']:>3} 条  {d['share']:>5.0%}  "
              f"平均重要性 {d['avg_importance']}")

    raw = report["separability_raw"]
    sep = report["separability"]
    print("\n[2] 可分性（只看文本，能否预测层归属）")
    print(f"  多数类基线         : {sep['majority_baseline']}")
    print(f"  含层名（泄漏，对照）: {raw['cv_accuracy']}  高于基线 {raw['lift_over_baseline']:+.3f}")
    print(f"  抹掉层名（诚实值）  : {sep['cv_accuracy']}  高于基线 {sep['lift_over_baseline']:+.3f}")
    if sep["lift_over_baseline"] > 0.1:
        print("  → 抹掉层名后仍显著高于基线：三层确实编码了可区分的语义")
    elif sep["lift_over_baseline"] > 0.03:
        print("  → 略高于基线：有一定信息量，但需扩大样本再判")
    else:
        print("  → 接近基线：可分区性主要来自层名本身，语义区分很弱")

    print("\n[3] 各层代表性特征（lift 越高越是该层独有）")
    for layer, terms in report["distinctive_terms"].items():
        joined = "、".join(t["term"] for t in terms[:6]) or "（样本不足）"
        print(f"  {layer:<10} {joined}")

    print(f"\n[注意] {report['caveat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
