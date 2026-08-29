"""
agent/citations.py — 引用校验（压幻觉的关键一环）

为什么需要它：
「可信的个人代理」这个定位，最大的敌人不是检索不到，而是**编**。
竞品在这上面栽得很彻底：LongMemEval 专门设了 Abstention 类别来测
"该说不知道时会不会编"，MemFail 的 Persona-Retrieval 里 52.3% 的查询
是误导性的，系统却拿无关实体的档案作答。

做法：回答必须带 `[ref:xxxx]`，代码校验每个引用是否来自**本次检索结果**。
引用了本次没检索到的 uuid = 凭空捏造，必须拦下。

注意边界：本模块只校验**引用合法性**，不校验事实正确性。
一个回答可以引用合法但内容失真（例如过度概括），那是另一个问题
（见竞品常见的 Over-Compression 失败模式），不要指望一个指标包打天下。
"""

from __future__ import annotations

import re

# 统一用 `[ref:xxx]`：L1 是 uuid（十六进制+连字符），L0 是 eid（ep_2026-03-11_0000，
# 含下划线），用不同标记会让调用方和校验逻辑各写一套。
_CITE_RE = re.compile(r"\[ref:([0-9a-zA-Z_\-]{4,40})\]")


def extract_citations(text: str) -> list[str]:
    """从回答文本中抽出所有被引用的 uuid（保留原始大小写，去重后排序）。"""
    return sorted({m.group(1).lower() for m in _CITE_RE.finditer(text or "")})


def validate_citations(answer: str, allowed: list[str] | set[str]) -> dict:
    """校验回答的引用是否都来自本次检索结果。

    allowed: 本次检索返回的 uuid 集合（可传完整 uuid 或前 8 位）。

    返回：
        cited   —— 回答里出现的引用
        illegal —— 不在 allowed 里的引用（即幻觉）
        ok      —— 是否全部合法
        uncited —— 检索到了但回答没用到的（不算错，仅提示）

    关于前缀匹配：注入 prompt 时用的是 uuid 前 8 位，所以校验时
    allowed 里的完整 uuid 要能与被引用片段前缀匹配上。
    """
    allowed_norm = {a.lower() for a in (allowed or [])}
    cited = extract_citations(answer)

    def _known(c: str) -> bool:
        if c in allowed_norm:
            return True
        return any(a.startswith(c) for a in allowed_norm)

    illegal = sorted({c for c in cited if not _known(c)})
    used = {c for c in cited if _known(c)}
    uncited = sorted(
        a for a in allowed_norm
        if not any(u.startswith(a) or a.startswith(u) for u in used)
    )
    return {
        "cited": cited,
        "illegal": illegal,
        "ok": not illegal,
        "uncited": uncited,
    }


def short_uuid(uuid_str: str, n: int = 8) -> str:
    """注入 prompt 用的短 uuid——太长会白白吃掉上下文。"""
    return (uuid_str or "")[:n]
