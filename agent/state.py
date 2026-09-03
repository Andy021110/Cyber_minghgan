"""
agent/state.py — LangGraph 图状态定义

设计依据（docs/LangGraph编排设计.md 第 2 节）：
- 短期记忆（thread-scoped）：messages + working_summary，由 checkpointer 持久化
- 长期记忆：不在 state 里常驻，只在需要时检索后放入 retrieved（避免污染上下文）
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class CyberState(TypedDict):
    """赛博明翰 Agent 的图状态。

    messages:        对话消息流（add_messages reducer 自动追加）
    working_summary: 短期记忆压缩摘要（滚动更新）
    retrieved:       本轮从长期记忆检索到的上下文（只在本轮有效）
    retrieved_refs:  本轮检索结果的引用标识列表（供 verify 校验引用合法性，A2）
    citation_check:  上一轮引用校验的结果（供前端提示，不阻断流程）
    turn:            当前轮次计数
    pending_question: HITL 追问内容（用于需要二次确认的场景）
    compacted_upto:  前 compacted_upto 条消息已被压进 working_summary（避免重复压缩）
    """

    messages: Annotated[list[AnyMessage], add_messages]
    working_summary: str
    retrieved: str
    retrieved_refs: list[str]
    citation_check: dict
    turn: int
    pending_question: str
    compacted_upto: int


def initial_state(user_text: str) -> CyberState:
    """构造一次对话的完整初始状态。

    仅在「明确要重置一个线程」时使用。续接已有线程请改用 new_turn()——
    传入完整状态会把 checkpointer 里已持久化的 turn / working_summary / compacted_upto
    覆盖回 0，这是 LangGraph 增量更新语义下的坑。
    """
    from langchain_core.messages import HumanMessage

    return CyberState(
        messages=[HumanMessage(content=user_text)],
        working_summary="",
        retrieved="",
        retrieved_refs=[],
        citation_check={},
        turn=0,
        pending_question="",
        compacted_upto=0,
    )


def new_turn(user_text: str) -> dict:
    """一轮对话的增量输入：只带新消息，其余字段交给 checkpointer 里已有的状态。"""
    from langchain_core.messages import HumanMessage

    return {"messages": [HumanMessage(content=user_text)]}
