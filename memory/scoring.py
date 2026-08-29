"""
memory/scoring.py — 中文检索打分（无外部依赖）

为什么单独成一个模块：
KG（cyber_planner）与 L0 原文（episodic_store）都需要同一套打分。
但 `cyber_planner` 依赖 `memory.episodic_store`，反过来 import 就是循环依赖。
所以打分逻辑下沉到这里，两边都从同一个地方取。

算法：字符 n-gram + 平滑 IDF 加权。为什么不是别的：
- 不用 `query in text`：中文不分词，整句作子串几乎必然不存在，
  实测自然问句命中恒为 0（BC-001）。
- 不用分词库：避免 jieba / sentence-transformers 这类外部依赖，
  本环境装不上（HF 不可达）。
- 用 IDF 而非纯覆盖率：否则「喜欢」这类高频片段淹没一切，
  导致无答案的问题也能召回一堆噪声，"该弃权时弃不了"。
"""

from __future__ import annotations

import math
import re

_PUNC_RE = re.compile(r"[\s，。？！、；：,.?!;:\"'（）()《》\[\]【】—…·]")


def normalize_text(s: str) -> str:
    """去标点与空白，统一小写——让打分不受书写差异影响。"""
    return _PUNC_RE.sub("", (s or "").lower())


def _grams(s: str, n: int = 2) -> set[str]:
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def keyword_score(query: str, text: str, n: int = 2) -> float:
    """单文档打分：命中的 n-gram 占比（0~1）。主要用于测试与简单场景。"""
    q, t = normalize_text(query), normalize_text(text)
    if not q or not t:
        return 0.0
    if len(q) < n:
        return 1.0 if q in t else 0.0
    grams = [q[i:i + n] for i in range(len(q) - n + 1)]
    return sum(1 for g in grams if g in t) / len(grams)


def keyword_scores_idf(query: str, texts: list[str], n: int = 2) -> list[float]:
    """对一批文档算 **IDF 加权** 的 n-gram 分数，返回与 texts 等长的分数表。

    返回的是「平均命中 IDF」而非归一化覆盖率。**这条很关键**：
    若除以 idf 总和归一化，任何 query 全命中时都得 1.0，
    罕见词与高频词无法区分，跨 query 的分数就不可比，
    门槛（kw_min_score）也就形同虚设。除以 gram 数得到平均命中 IDF，
    罕见词天然分高，分数因此可跨 query 比较。
    """
    N = len(texts)
    if N == 0:
        return []
    q = normalize_text(query)
    if not q:
        return [0.0] * N

    normed = [normalize_text(t) for t in texts]

    # 查询过短（去标点后不足 n 字）切不出 gram，退化为子串匹配。
    # 不能沿用 _grams(q, n)——它返回的是单字集合，而文档侧只按 2-gram 表示，
    # 两者永远匹配不上，导致所有单字查询恒为 0（实测 search("x") 返回空）。
    if len(q) < n:
        df_q = sum(1 for t in normed if q in t)
        idf_q = math.log((N + 1) / (1 + df_q)) + 1.0
        return [idf_q if q in t else 0.0 for t in normed]

    q_grams = _grams(q, n)
    if not q_grams:
        return [0.0] * N
    df: dict[str, int] = {}
    for t in normed:
        for g in _grams(t, n):
            df[g] = df.get(g, 0) + 1

    idf = {g: math.log((N + 1) / (1 + df.get(g, 0))) + 1.0 for g in q_grams}

    scores = []
    for t in normed:
        t_grams = _grams(t, n)
        hit = sum(w for g, w in idf.items() if g in t_grams)
        scores.append(hit / len(q_grams))
    return scores
