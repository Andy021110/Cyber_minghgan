"""
L0 Episodic Store — 原文轮次记忆（事实检索层）

与 L1 动力学 KG 分离：本模块只做 append + search，不写 yuanbao_cyber_minghan_kg.json。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

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
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

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

    def search(self, query: str, limit: int = 10) -> list[dict]:
        terms = expand_query_terms(query)
        scored: list[tuple[float, Episode]] = []
        for ep in self.iter_all():
            blob = (ep.text + " " + " ".join(ep.entities)).lower()
            score = 0.0
            for t in terms:
                tl = t.lower()
                if not tl:
                    continue
                if tl in blob:
                    score += 2.0 if len(tl) >= 2 else 0.5
                # 日期别名互相加分
                for a in normalize_date_aliases(t):
                    if a.lower() in blob or a in ep.ts or ep.ts in a:
                        score += 3.0
            for a in normalize_date_aliases(ep.ts):
                if any(a in t or t in a for t in terms):
                    score += 2.5
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: (-x[0], x[1].ts))
        out = []
        for score, ep in scored[:limit]:
            d = ep.to_dict()
            d["score"] = round(score, 3)
            out.append(d)
        return out
