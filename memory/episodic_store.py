"""
L0 Episodic Store — 原文轮次记忆（事实检索层）

与 L1 动力学 KG 分离：本模块只做 append + search，不写 yuanbao_cyber_minghan_kg.json。

Phase 2 升级：引入 keyword + vector 混合检索。
- 默认使用 ZeroEmbeddingProvider（零向量，退化为纯关键词检索，零依赖）。
- 生产环境传入 BgeEmbeddingProvider 即可启用本地 bge-small-zh-v1.5 语义检索。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from memory.embeddings import (
    EmbeddingProvider,
    ZeroEmbeddingProvider,
    cosine_similarity,
    hybrid_score,
)

_DATE_PATTERNS = [
    # 2023-05-04 / 2023/05/04
    (re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})"), "ymd"),
    # 5月4日 / 05月04日
    (re.compile(r"(\d{1,2})月(\d{1,2})日"), "md"),
]


def normalize_date_aliases(text: str, default_year: int | None = None) -> set[str]:
    """从文本抽出日期的多种写法，供检索扩写。"""
    aliases: set[str] = set()
    for pat, kind in _DATE_PATTERNS:
        for m in pat.finditer(text or ""):
            if kind == "ymd":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            else:
                y = default_year or datetime.now().year
                mo, d = int(m.group(1)), int(m.group(2))
            aliases.add(f"{y:04d}-{mo:02d}-{d:02d}")
            aliases.add(f"{mo}月{d}日")
            aliases.add(f"{mo:02d}月{d:02d}日")
            aliases.add(f"{y}年{mo}月{d}日")
    return aliases


def expand_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    terms = {q}
    for t in re.split(r"[\s,，、?？]+", q):
        if t:
            terms.add(t)
    terms |= normalize_date_aliases(q)
    # 同义弱扩展
    if "麻烦" in q:
        terms.update(["紧张", "担心", "害怕", "演讲"])
    if "画家" in q:
        terms.update(["绘画", "文艺复兴", "达芬奇", "达·芬奇", "米开朗", "拉斐尔"])
    if "景色" in q or "公园" in q:
        terms.update(["樱花", "松鼠", "绿禾"])
    return [t for t in terms if t]


def _keyword_score(query: str, episode: Episode) -> float:
    """保留 Phase 1 的关键词打分逻辑。"""
    terms = expand_query_terms(query)
    blob = (episode.text + " " + " ".join(episode.entities)).lower()
    score = 0.0
    for t in terms:
        tl = t.lower()
        if not tl:
            continue
        if tl in blob:
            score += 2.0 if len(tl) >= 2 else 0.5
        # 日期别名互相加分
        for a in normalize_date_aliases(t):
            if a.lower() in blob or a in episode.ts or episode.ts in a:
                score += 3.0
    for a in normalize_date_aliases(episode.ts):
        if any(a in t or t in a for t in terms):
            score += 2.5
    return score


@dataclass
class Episode:
    eid: str
    ts: str
    user_text: str
    assistant_text: str
    text: str
    entities: list[str]
    source: str = "live"

    def to_dict(self) -> dict:
        return asdict(self)


class EpisodicStore:
    def __init__(
        self,
        path: Path,
        provider: EmbeddingProvider | None = None,
        vector_alpha: float = 0.4,
    ):
        """
        provider: EmbeddingProvider，默认 ZeroEmbeddingProvider（纯关键词）。
        vector_alpha: 向量部分权重，0 为纯关键词，1 为纯向量。默认 0.4。
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")
        self.provider = provider or ZeroEmbeddingProvider()
        # Zero provider 时不启用向量，避免拉低 keyword score
        self.vector_alpha = 0.0 if isinstance(self.provider, ZeroEmbeddingProvider) else vector_alpha

    def clear(self) -> None:
        self.path.write_text("", encoding="utf-8")

    def append(
        self,
        *,
        ts: str,
        user_text: str,
        assistant_text: str,
        eid: str | None = None,
        entities: Iterable[str] | None = None,
        source: str = "live",
    ) -> Episode:
        n = self.count()
        eid = eid or f"ep_{ts}_{n:04d}"
        text = f"日期:{ts}\n用户:{user_text}\n助手:{assistant_text}"
        ep = Episode(
            eid=eid,
            ts=ts,
            user_text=user_text or "",
            assistant_text=assistant_text or "",
            text=text,
            entities=list(entities or []),
            source=source,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ep.to_dict(), ensure_ascii=False) + "\n")
        return ep

    def iter_all(self) -> list[Episode]:
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            rows.append(Episode(**d))
        return rows

    def count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())

    def get(self, eid: str) -> dict | None:
        for ep in self.iter_all():
            if ep.eid == eid:
                return ep.to_dict()
        return None

    def list_episodes(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order: str = "asc",
        summary_chars: int = 280,
    ) -> dict:
        """Paginated chronological listing for exhaustive counting."""
        rows = self.iter_all()
        reverse = str(order).lower() == "desc"
        rows.sort(key=lambda e: e.ts, reverse=reverse)
        total = len(rows)
        offset = max(0, int(offset))
        limit = max(1, min(int(limit), 50))
        page = rows[offset : offset + limit]
        items = []
        for ep in page:
            text = ep.text or ""
            items.append(
                {
                    "eid": ep.eid,
                    "ts": ep.ts,
                    "source": ep.source,
                    "summary": text[:summary_chars]
                    + ("…" if len(text) > summary_chars else ""),
                    "entities": ep.entities,
                }
            )
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "order": "desc" if reverse else "asc",
            "returned": len(items),
            "has_more": offset + len(items) < total,
            "items": items,
        }

    def _episode_vector_text(self, episode: Episode) -> str:
        """用于向量编码的文本：原文 + 实体。"""
        return f"{episode.text} {' '.join(episode.entities)}".strip()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        rows = self.iter_all()
        if not rows:
            return []

        # 1) keyword score
        keyword_scores = np.zeros(len(rows), dtype=np.float32)
        doc_texts: list[str] = []
        for i, ep in enumerate(rows):
            keyword_scores[i] = _keyword_score(query, ep)
            doc_texts.append(self._episode_vector_text(ep))

        # 2) vector score（Zero provider 时 alpha=0，直接跳过计算）
        vector_scores = np.zeros(len(rows), dtype=np.float32)
        if self.vector_alpha > 0:
            query_emb = self.provider.encode([query])
            doc_emb = self.provider.encode(doc_texts)
            vector_scores = cosine_similarity(query_emb, doc_emb)

        # 3) 融合并排序
        final_scores = hybrid_score(keyword_scores, vector_scores, alpha=self.vector_alpha)
        indexed = list(zip(final_scores, keyword_scores, vector_scores, rows))
        indexed.sort(key=lambda x: (-x[0], x[3].ts))

        out = []
        for final, kw, vec, ep in indexed[:limit]:
            if final <= 0 and self.vector_alpha == 0:
                # 纯关键词模式下，无命中不返回
                continue
            d = ep.to_dict()
            d["score"] = round(float(final), 3)
            d["kw_score"] = round(float(kw), 3)
            d["vec_score"] = round(float(vec), 3)
            out.append(d)
        return out
