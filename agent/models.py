"""
agent/models.py — LLM 适配层

目的：让图编排不绑定具体 SDK。
- ChatModel 协议：invoke(messages, tools) -> AIMessage
- FakeChatModel：测试用，脚本化返回，零 API 调用
- AnthropicChatAdapter：真实调用（anthropic SDK，兼容 DeepSeek 的 Anthropic 网关）
"""

from __future__ import annotations

from typing import Any, Protocol

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage


class ChatModel(Protocol):
    """图节点只依赖这个协议。"""

    def invoke(self, messages: list[AnyMessage], tools: list[dict] | None = None) -> AIMessage:
        ...


class FakeChatModel:
    """脚本化假模型：按 script 顺序返回 AIMessage，记录所有调用便于断言。"""

    def __init__(self, script: list[AIMessage] | None = None):
        self.script = list(script or [])
        self.calls: list[dict] = []

    def invoke(self, messages: list[AnyMessage], tools: list[dict] | None = None) -> AIMessage:
        self.calls.append({"messages": list(messages), "tools": tools})
        if self.script:
            return self.script.pop(0)
        return AIMessage(content="（fake 默认回复）")


def _to_anthropic_messages(
    messages: list[AnyMessage],
) -> tuple[str, list[dict]]:
    """LangChain 消息 → Anthropic API 格式（system 单独抽出）。

    关键约束：**同一条 assistant 消息里的所有 tool_use，必须在紧邻的
    下一条 user 消息里配齐全部 tool_result**——缺一个就 400 报错。

    所以连续的 tool 消息必须**累积**，遇到非 tool 消息时一次性 flush 成
    单条 user 消息。若各自转成独立的 user 消息，一轮调 2 个工具就变成
    「assistant[2 个 tool_use] → user[result1] → user[result2]」，
    第二个 tool_use 找不到紧邻的 result，API 直接拒绝（BC-015）。
    """
    system_parts: list[str] = []
    out: list[dict] = []
    pending_tools: list[dict] = []

    def _flush_tools() -> None:
        if pending_tools:
            out.append({"role": "user", "content": list(pending_tools)})
            pending_tools.clear()

    for m in messages:
        role = getattr(m, "type", "")
        if role == "system":
            system_parts.append(str(m.content))
            continue
        if role == "human":
            _flush_tools()
            out.append({"role": "user", "content": str(m.content)})
            continue
        if role == "tool":
            pending_tools.append(
                {
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": str(m.content),
                }
            )
            continue
        if role == "ai":
            _flush_tools()
            blocks: list[dict] = []
            text = m.content if isinstance(m.content, str) else ""
            if text:
                blocks.append({"type": "text", "text": text})
            for tc in getattr(m, "tool_calls", []) or []:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "input": tc.get("args", {}),
                    }
                )
            if not blocks:
                blocks.append({"type": "text", "text": ""})
            out.append({"role": "assistant", "content": blocks})
            continue
        # 兜底：未知类型当作用户消息
        _flush_tools()
        out.append({"role": "user", "content": str(getattr(m, "content", ""))})

    _flush_tools()          # 结尾若还挂着 tool_result 不能丢
    return "\n".join(system_parts), out


class AnthropicChatAdapter:
    """真实 LLM 适配器，包装 anthropic SDK。"""

    def __init__(self, client: Any, model: str, max_tokens: int = 2048, system: str = ""):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.system = system

    def invoke(self, messages: list[AnyMessage], tools: list[dict] | None = None) -> AIMessage:
        inline_system, api_messages = _to_anthropic_messages(messages)
        system = self.system or inline_system

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": api_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        resp = self.client.messages.create(**kwargs)

        text = ""
        tool_calls: list[dict] = []
        for block in getattr(resp, "content", []) or []:
            btype = getattr(block, "type", "")
            if btype == "text":
                text += getattr(block, "text", "")
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "name": block.name,
                        "args": dict(block.input or {}),
                        "id": block.id,
                    }
                )
        return AIMessage(content=text, tool_calls=tool_calls)


__all__ = [
    "AIMessage",
    "AnthropicChatAdapter",
    "ChatModel",
    "FakeChatModel",
    "SystemMessage",
    "ToolMessage",
]
