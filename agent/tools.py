"""
agent/tools.py — 把既有的 L0/L1 记忆操作包装成 LangGraph 可调度工具

原则（docs/LangGraph编排设计.md 第 6 节）：
- 不重写数据层，复用 CyberBrainStore / EpisodicStore
- 工具描述沿用 CYBER_TOOLS 的语义，避免 LLM 行为漂移
- 写类工具单独分组，供 hitl_gate 拦截
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool

from memory.episodic_store import EpisodicStore

READ_TOOL_NAMES = ("retrieve_memory", "retrieve_episode", "list_episodes")
WRITE_TOOL_NAMES = ("create_memory", "update_memory", "delete_memory")


def build_tools(store: Any, episodic: EpisodicStore) -> tuple[list[BaseTool], list[BaseTool]]:
    """返回 (读工具, 写工具)。闭包绑定 store，便于测试注入临时实例。"""

    @tool
    def retrieve_memory(keyword: str, limit: int = 10) -> str:
        """在三层心智图谱（Id/Ego/Superego）中做关键词+向量混合检索，返回匹配节点的精简摘要。
        询问偏好、习惯、情感模式、行为规律等「关于赛博明翰自己」的问题时，必须先调用它。"""
        hits = store.retrieve(keyword, limit=limit)
        if not hits:
            return "无匹配节点。"
        return json.dumps(hits, ensure_ascii=False)

    @tool
    def retrieve_episode(keyword: str, limit: int = 10) -> str:
        """在 L0 原文对话记忆中检索具体事实、说过的话、日期、数量等细节。"""
        hits = episodic.search(keyword, limit=limit)
        if not hits:
            return "无匹配轮次。"
        return json.dumps(hits, ensure_ascii=False)

    @tool
    def list_episodes(offset: int = 0, limit: int = 20) -> str:
        """按时间顺序列举 L0 原文轮次（用于计数、聚合、排序，关键词可能漏召回时用）。"""
        return json.dumps(
            episodic.list_episodes(offset=offset, limit=limit),
            ensure_ascii=False,
        )

    @tool
    def create_memory(
        layer: Annotated[str, "目标层级：Id / Superego / Ego"],
        event_label: Annotated[str, "节点的语义标签"],
        description: Annotated[str, "分析性描述，80~150 字"],
        evidence: Annotated[str, "触发该动力学的原始对话证据，不可为空"],
    ) -> str:
        """向心智图谱追加一条新的动力学记忆节点。仅在确认图谱尚无此信息时调用。"""
        node = store.create(
            layer=layer,
            event_label=event_label,
            description=description,
            evidence=evidence,
            batch_id="LangGraph",
            importance=5,
            source_mode="langgraph",
        )
        return json.dumps({"uuid": node.get("uuid", ""), "label": node.get("event_label", "")},
                          ensure_ascii=False)

    @tool
    def update_memory(
        node_uuid: Annotated[str, "目标节点 uuid，必须通过 retrieve_memory 获得"],
        description: str = "",
        evidence: str = "",
        event_label: str = "",
    ) -> str:
        """按 uuid 更新已有节点的描述/证据/标签。uuid 与 layer 为只读字段。"""
        fields: dict[str, Any] = {}
        if description:
            fields["description"] = description
        if evidence:
            fields["evidence"] = evidence
        if event_label:
            fields["event_label"] = event_label
        node = store.update(node_uuid, **fields)
        return json.dumps({"uuid": node.get("uuid", ""), "updated": sorted(fields)},
                          ensure_ascii=False)

    @tool
    def delete_memory(
        node_uuid: Annotated[str, "目标节点 uuid，必须通过 retrieve_memory 获得"],
    ) -> str:
        """按 uuid 永久删除节点。仅用于确认重复或错误录入的记忆，不可撤销。"""
        store.delete(node_uuid)
        return "已删除。"

    read_tools: list[BaseTool] = [retrieve_memory, retrieve_episode, list_episodes]
    write_tools: list[BaseTool] = [create_memory, update_memory, delete_memory]
    return read_tools, write_tools


def to_anthropic_tools(tools: list[BaseTool]) -> list[dict]:
    """LangChain 工具 → Anthropic tool schema（供 AnthropicChatAdapter 透传）。"""
    out = []
    for t in tools:
        schema = t.args_schema.model_json_schema() if t.args_schema else {
            "type": "object", "properties": {}
        }
        out.append(
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": schema,
            }
        )
    return out
