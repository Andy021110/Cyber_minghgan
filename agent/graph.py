"""
agent/graph.py — 赛博明翰的 LangGraph 编排

图结构（详见 docs/LangGraph编排设计.md 第 3 节）：

    START → load_memory → agent →(写工具)→ hitl_gate ═interrupt═→ write_back → agent
                                  └─(读工具)→ read_tools ─────────────────────┘
                                  └─(无工具)→ persist → END

HITL 硬约束（官方 Interrupts 文档，已写进注释防止后人改坏）：
1. hitl_gate 内 interrupt() 之前不得有任何副作用 —— 节点恢复时会从头重跑
2. 禁止用 try/except 包裹 interrupt() —— 会吞掉暂停异常
3. 一个节点内只调一次 interrupt() —— 多轮追问走 pending_question + 条件边
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from agent.citations import validate_citations
from agent.memory import retrieve_long_term_with_refs
from agent.state import CyberState
from agent.tools import WRITE_TOOL_NAMES, build_tools, to_anthropic_tools

DEFAULT_SYSTEM = "你是赛博明翰。回答前先检索记忆，无依据就说不知道，禁止编造。"

_APPROVE_ALIASES = {"approved_kg", "approve", "approved", "yes", "y", "ok", "true"}
_LOG_ALIASES = {"approved_log", "log"}


def _normalize_decision(value: Any) -> str:
    """把人工审批的返回值归一到三档语义。"""
    if value is True:
        return "approved_kg"
    if value is False or value is None:
        return "rejected"
    s = str(value).strip().lower()
    if s in _APPROVE_ALIASES:
        return "approved_kg"
    if s in _LOG_ALIASES:
        return "approved_log"
    return "rejected"


def _last_human_text(messages: list[AnyMessage]) -> str:
    for m in reversed(messages):
        if getattr(m, "type", "") == "human":
            return str(m.content)
    return ""


def compose_system(base: str, summary: str, retrieved: str) -> str:
    """拼装系统提示：人设 + 短期记忆摘要 + 长期记忆检索结果。"""
    parts = [base or DEFAULT_SYSTEM]
    if summary:
        parts.append(f"【短期记忆 · 前文摘要】\n{summary}")
    if retrieved:
        parts.append(f"【长期记忆 · 本轮检索】\n{retrieved}")
    return "\n\n".join(parts)


def build_graph(
    llm: Any,
    store: Any,
    episodic: Any,
    system_prompt: str = DEFAULT_SYSTEM,
    checkpointer: Any = None,
    keep_last: int = 6,
    compact_threshold: int = 12,
):
    """编译并返回 LangGraph 图。

    llm:        满足 ChatModel 协议的对象（FakeChatModel / AnthropicChatAdapter）
    store:      CyberBrainStore（L1）
    episodic:   EpisodicStore（L0）
    checkpointer: 短期记忆持久化，默认 InMemorySaver（生产建议 SqliteSaver）
    """
    read_tools, write_tools = build_tools(store, episodic)
    all_tools = read_tools + write_tools
    anthropic_tools = to_anthropic_tools(all_tools)
    read_by_name = {t.name: t for t in read_tools}
    write_by_name = {t.name: t for t in write_tools}
    read_node = ToolNode(read_tools)

    def load_memory(state: CyberState) -> dict:
        """注入长期记忆检索结果。只读，无副作用。"""
        query = _last_human_text(state["messages"])
        retrieved, refs = retrieve_long_term_with_refs(query, store, episodic)
        return {"retrieved": retrieved, "retrieved_refs": refs}

    def agent_node(state: CyberState) -> dict:
        """LLM 决策节点：决定说话还是调工具。"""
        window = state["messages"][state.get("compacted_upto", 0):]
        prompt = compose_system(system_prompt, state.get("working_summary", ""),
                                state.get("retrieved", ""))
        msgs: list[AnyMessage] = [SystemMessage(content=prompt)] + list(window)
        resp = llm.invoke(msgs, tools=anthropic_tools)
        return {"messages": [resp]}

    def route_after_agent(state: CyberState) -> str:
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
        if not calls:
            return "persist"
        names = {c.get("name", "") for c in calls}
        if names & set(WRITE_TOOL_NAMES):
            return "hitl_gate"
        return "read_tools"

    def hitl_gate(state: CyberState) -> Command:
        """写类工具的审批闸门。

        注意：interrupt() 之前绝不能有副作用（节点恢复时会整段重跑）。
        也禁止用 try/except 包裹 interrupt()，否则暂停异常被吞。
        """
        last = state["messages"][-1]
        calls = list(getattr(last, "tool_calls", None) or [])
        writes = [c for c in calls if c.get("name") in WRITE_TOOL_NAMES]

        payload = {
            "question": "即将写入长期记忆，是否批准？",
            "writes": [{"name": c["name"], "args": c.get("args", {})} for c in writes],
        }
        decision_raw = interrupt(payload)
        decision = _normalize_decision(decision_raw)

        results: list[ToolMessage] = []
        for c in calls:
            name = c.get("name", "")
            call_id = c.get("id", "")
            args = c.get("args", {}) or {}
            if name in write_by_name:
                if decision == "approved_kg":
                    try:
                        content = str(write_by_name[name].invoke(args))
                    except Exception as exc:  # 工具内部异常要回传给 LLM，不能崩图
                        content = f"写入失败：{exc}"
                elif decision == "approved_log":
                    content = "已记录到日志，未写入图谱。"
                else:
                    content = "用户拒绝，未写入长期记忆。"
            elif name in read_by_name:
                try:
                    content = str(read_by_name[name].invoke(args))
                except Exception as exc:
                    content = f"检索失败：{exc}"
            else:
                content = f"未知工具：{name}"
            results.append(ToolMessage(content=content, tool_call_id=call_id))

        return Command(goto="agent", update={"messages": results})

    def verify(state: CyberState) -> dict:
        """回答落盘前校验引用（A2 压幻觉）。

        只做校验与标注，**绝不自动改写内容**——自动改写会引入新的幻觉
        （改出来的话同样没人验证过），而且用户不知道发生过什么。
        非法引用的处理交给上层决定：提示用户、或要求重新生成。

        注意这里拦的是 8月9日跑分里那类 HALLUC_EMPTY：记忆库为空时模型
        照样编出"北邮，北京邮电大学"。检索层对这种情况无能为力（无米下锅），
        只有生成层的引用校验能发现——它拿不出任何 [ref:]。
        """
        msgs = list(state["messages"])
        answer = ""
        for m in reversed(msgs):
            if getattr(m, "type", "") == "ai":
                answer = m.content if isinstance(m.content, str) else ""
                break
        if not answer:
            return {}
        return {
            "citation_check": validate_citations(
                answer, state.get("retrieved_refs", [])
            )
        }

    def persist(state: CyberState) -> dict:
        """回合结束：L0 落盘 + 短期记忆压缩。"""
        msgs = list(state["messages"])
        user_text = _last_human_text(msgs)
        assistant_text = ""
        for m in reversed(msgs):
            if getattr(m, "type", "") == "ai":
                assistant_text = m.content if isinstance(m.content, str) else ""
                break

        if episodic is not None and (user_text or assistant_text):
            try:
                episodic.append(
                    ts=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    user_text=user_text,
                    assistant_text=assistant_text,
                    source="langgraph",
                )
            except Exception:
                pass

        update: dict = {"turn": int(state.get("turn", 0)) + 1}

        # 短期记忆压缩：只压「窗口之外且尚未压过」的部分
        upto = int(state.get("compacted_upto", 0))
        cut = max(0, len(msgs) - keep_last)
        if len(msgs) - upto > compact_threshold and cut > upto:
            new_summary, _ = compact(
                state.get("working_summary", ""), msgs[upto:cut], llm, keep_last=0
            )
            update["working_summary"] = new_summary
            update["compacted_upto"] = cut
        return update

    g = StateGraph(CyberState)
    g.add_node("load_memory", load_memory)
    g.add_node("agent", agent_node)
    g.add_node("read_tools", read_node)
    g.add_node("hitl_gate", hitl_gate)
    g.add_node("verify", verify)
    g.add_node("persist", persist)

    g.add_edge(START, "load_memory")
    g.add_edge("load_memory", "agent")
    g.add_conditional_edges(
        "agent",
        route_after_agent,
        {"read_tools": "read_tools", "hitl_gate": "hitl_gate", "persist": "verify"},
    )
    g.add_edge("read_tools", "agent")
    g.add_edge("verify", "persist")
    g.add_edge("persist", END)

    return g.compile(checkpointer=checkpointer or InMemorySaver())


__all__ = ["build_graph", "compose_system", "to_anthropic_tools"]
