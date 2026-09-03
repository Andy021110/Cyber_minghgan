"""
agent/memory.py — 长期记忆检索 + 短期记忆压缩

对应 docs/LangGraph编排设计.md 第 2、5 节：
- retrieve_long_term：跨会话取回 L1 语义（KG）与 L0 情景（原文），只在当轮注入
- compact_*：短期记忆（working_summary）滚动压缩，防止上下文无限膨胀
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage

from agent.citations import short_uuid


def _format_l1(hits: list[dict], limit: int = 5) -> str:
    """格式化 L1 命中项。

    每条都带 `[ref:xxxx]`——**这是引用校验的前提**。
    之前只输出 layer/label/description，LLM 根本无从引用，
    于是"回答要带引用"这条要求只能靠模型编一个 uuid 来应付。
    """
    if not hits:
        return ""
    lines = []
    for h in hits[:limit]:
        ref = short_uuid(h.get("uuid", "")) or "?"
        lines.append(
            f"- [ref:{ref}] [{h.get('layer', '?')}] "
            f"{h.get('event_label', '')}: {h.get('description', '')}"
        )
    return "\n".join(lines)


def _format_l0(hits: list[dict], limit: int = 5, chars: int = 120) -> str:
    if not hits:
        return ""
    lines = []
    for h in hits[:limit]:
        user = (h.get("user_text") or "").replace("\n", " ")[:chars]
        asst = (h.get("assistant_text") or "").replace("\n", " ")[:chars]
        ref = h.get("eid") or "?"
        lines.append(f"- [ref:{ref}] {h.get('ts', '')} 用户: {user}｜助手: {asst}")
    return "\n".join(lines)


def retrieve_long_term(
    query: str,
    store: Any,
    episodic: Any,
    l1_limit: int = 5,
    l0_limit: int = 5,
) -> str:
    """混合检索 L1 + L0，返回可直接注入 system prompt 的文本块。"""
    text, _ = retrieve_long_term_with_refs(
        query, store, episodic, l1_limit, l0_limit
    )
    return text


def retrieve_long_term_with_refs(
    query: str,
    store: Any,
    episodic: Any,
    l1_limit: int = 5,
    l0_limit: int = 5,
) -> tuple[str, list[str]]:
    """同上，但同时返回本轮检索到的**引用标识列表**。

    refs 是 A2 引用校验的依据：回答里出现的 `[ref:xxx]` 必须来自这个列表，
    否则就是凭空编造。

    这条针对的是 8月9日 A 类跑分暴露的 HALLUC_EMPTY——记忆库为空时，
    模型照样答出"北邮，北京邮电大学"。那种情况检索层根本无从拦截
    （无米下锅），只能靠生成层的引用校验：拿不出 [ref:] 就判定非法。
    """
    sections: list[str] = []
    refs: list[str] = []
    if store is not None:
        hits = store.retrieve(query, limit=l1_limit)
        text = _format_l1(hits, l1_limit)
        if text:
            sections.append(f"【L1 语义记忆 · 命中 {len(hits)}】\n{text}")
            refs += [short_uuid(h.get("uuid", ""))
                     for h in hits if h.get("uuid")]
    if episodic is not None:
        hits = episodic.search(query, limit=l0_limit)
        text = _format_l0(hits, l0_limit)
        if text:
            sections.append(f"【L0 情景记忆 · 命中 {len(hits)}】\n{text}")
            refs += [h.get("eid", "") for h in hits if h.get("eid")]
    return "\n\n".join(sections), refs


COMPACT_SYSTEM = (
    "你是记忆压缩器。给定【已有摘要】和【新增对话】，输出一份合并后的新摘要。\n"
    "要求：保留具体事实（人名、数字、日期、偏好）；丢弃寒暄与重复；中文；不超过 300 字。\n"
    "只输出新摘要本身，不要任何解释或前缀。"
)


def build_compact_messages(summary: str, to_compact: list[AnyMessage]) -> list[AnyMessage]:
    """构造压缩请求的消息列表（单独抽出，便于单测）。"""
    dialogue = []
    for m in to_compact:
        if isinstance(m, HumanMessage):
            dialogue.append(f"用户: {m.content}")
        elif isinstance(m, AIMessage):
            dialogue.append(f"赛博明翰: {m.content}")
    body = f"【已有摘要】\n{summary or '（空）'}\n\n【新增对话】\n" + "\n".join(dialogue)
    return [SystemMessage(content=COMPACT_SYSTEM), HumanMessage(content=body)]


def compact(
    summary: str,
    messages: list[AnyMessage],
    llm: Any,
    keep_last: int = 6,
) -> tuple[str, list[AnyMessage]]:
    """把较早的消息压进摘要，只保留最近 keep_last 条。

    llm 为 None 或调用失败时退化为「截断式兜底」，保证不会丢异常。
    """
    if len(messages) <= keep_last:
        return summary, messages

    to_compact = messages[:-keep_last]
    kept = messages[-keep_last:]

    new_summary = summary or ""
    if llm is not None:
        try:
            resp = llm.invoke(build_compact_messages(summary, to_compact))
            text = getattr(resp, "content", "") or ""
            if isinstance(text, str) and text.strip():
                new_summary = text.strip()
        except Exception:
            pass

    if not new_summary:
        # 兜底：把被压掉的内容按行拼到旧摘要后面
        tail = " / ".join(str(getattr(m, "content", ""))[:60] for m in to_compact)
        new_summary = (summary + " " + tail).strip()[:600]

    return new_summary, kept
