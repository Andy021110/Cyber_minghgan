"""Anthropic 消息转换的测试（BC-015）。

背景：只要 LLM 一轮调 2 个以上工具，核心对话链路就必崩——
tool_use 找不到紧邻的 tool_result。原因是每个 ToolMessage 被转成
了独立的 user 消息。Anthropic 要求同一条 assistant 消息里的所有
tool_use 必须在紧邻的下一条 user 消息里配齐全部 result。
"""

import pytest

from agent.models import _to_anthropic_messages
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


def _ai_with_two_calls():
    return AIMessage(
        content="",
        tool_calls=[
            {"id": "call_1", "name": "retrieve_memory", "args": {"q": "咖啡"}},
            {"id": "call_2", "name": "retrieve_episode", "args": {"q": "咖啡"}},
        ],
    )


def test_two_tool_results_merge_into_one_user_message():
    """核心用例：一轮两个工具，结果必须合并进同一条 user 消息。"""
    msgs = [
        HumanMessage(content="我喜欢喝什么咖啡？"),
        _ai_with_two_calls(),
        ToolMessage(content="结果A", tool_call_id="call_1"),
        ToolMessage(content="结果B", tool_call_id="call_2"),
    ]
    _, out = _to_anthropic_messages(msgs)

    # 结构应为：user / assistant(2 tool_use) / user(2 tool_result)
    assert len(out) == 3, f"应合并为 3 条，实际 {len(out)}"
    assert out[2]["role"] == "user"
    assert len(out[2]["content"]) == 2, "两个 result 必须在同一条消息里"
    ids = {b["tool_use_id"] for b in out[2]["content"]}
    assert ids == {"call_1", "call_2"}


def test_every_tool_use_has_adjacent_result():
    """直接断言 BC-015 的修复目标：没有孤立的 tool_use。"""
    msgs = [
        HumanMessage(content="问一句"),
        _ai_with_two_calls(),
        ToolMessage(content="结果A", tool_call_id="call_1"),
        ToolMessage(content="结果B", tool_call_id="call_2"),
    ]
    _, out = _to_anthropic_messages(msgs)

    for i, msg in enumerate(out):
        if msg["role"] == "assistant":
            wanted = {b["id"] for b in msg["content"]
                      if b.get("type") == "tool_use"}
            if wanted:
                nxt = out[i + 1]
                got = {b["tool_use_id"] for b in nxt["content"]
                       if b.get("type") == "tool_result"}
                assert wanted == got, f"第 {i} 条缺 result: {wanted - got}"


def test_single_tool_call_still_works():
    msgs = [
        HumanMessage(content="问一句"),
        AIMessage(content="", tool_calls=[
            {"id": "c1", "name": "retrieve_memory", "args": {}}]),
        ToolMessage(content="结果", tool_call_id="c1"),
    ]
    _, out = _to_anthropic_messages(msgs)
    assert len(out) == 3
    assert out[2]["content"][0]["tool_use_id"] == "c1"


def test_non_adjacent_tools_not_merged():
    """中间隔了人类消息的两批工具结果，不该被合并。"""
    msgs = [
        HumanMessage(content="第一问"),
        AIMessage(content="", tool_calls=[
            {"id": "c1", "name": "retrieve_memory", "args": {}}]),
        ToolMessage(content="结果1", tool_call_id="c1"),
        HumanMessage(content="第二问"),
        AIMessage(content="", tool_calls=[
            {"id": "c2", "name": "retrieve_memory", "args": {}}]),
        ToolMessage(content="结果2", tool_call_id="c2"),
    ]
    _, out = _to_anthropic_messages(msgs)
    roles = [m["role"] for m in out]
    assert roles == ["user", "assistant", "user", "user", "assistant", "user"]


def test_trailing_tool_results_not_dropped():
    """结尾挂着的 tool_result 不能因为没后续消息而丢失。"""
    msgs = [
        HumanMessage(content="问"),
        _ai_with_two_calls(),
        ToolMessage(content="结果A", tool_call_id="call_1"),
        ToolMessage(content="结果B", tool_call_id="call_2"),
    ]
    _, out = _to_anthropic_messages(msgs)
    assert out[-1]["role"] == "user"
    assert len(out[-1]["content"]) == 2


def test_system_message_extracted():
    msgs = [SystemMessage(content="你是助手"),
            HumanMessage(content="你好")]
    sys_txt, out = _to_anthropic_messages(msgs)
    assert "你是助手" in sys_txt
    assert len(out) == 1 and out[0]["role"] == "user"
