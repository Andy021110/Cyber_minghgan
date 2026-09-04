"""对话中学习（端到端）的测试。

这是个人助理**最核心的能力**：你说了一件它不知道的事，它记住；
下次全新会话再问，答得出来。没有这个，就只是个查询接口。

流程：说新事实 → LLM 调 create_memory → HITL 批准 → 写入 → 新会话能答。

用 FakeChatModel 模拟 LLM，避免每次跑测试都花 API 费用。
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from agent.graph import build_graph
from cyber_planner import CyberBrainStore
from memory.episodic_store import EpisodicStore


class ScriptedLLM:
    """按脚本返回消息的假 LLM：第一次调工具，第二次纯文本回复。"""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def invoke(self, messages, tools=None):
        self.seen.append(len(messages))
        return self.script.pop(0)


def _make(tmp_path, script):
    d = Path(tempfile.mkdtemp())
    shutil.copy("yuanbao_cyber_minghan_kg.json", d / "kg.json")
    store = CyberBrainStore(kg_path=d / "kg.json")
    epi = EpisodicStore(d / "epi.jsonl")
    g = build_graph(llm=ScriptedLLM(script), store=store,
                    episodic=epi, checkpointer=None)
    return g, store, d


def _write_call(cid="c1"):
    return AIMessage(content="", tool_calls=[{
        "id": cid, "name": "create_memory",
        "args": {"layer": "Ego", "event_label": "开始学吉他",
                 "description": "最近开始学吉他，每周三晚上上课。",
                 "evidence": "用户说：「我最近开始学吉他了」"},
    }])


def _ego_len(path):
    return len(json.loads(path.read_text(encoding="utf-8"))
               ["nodes"]["Cyber_Minghan"]["Ego_Dynamics"])


def test_approved_write_persists():
    """批准后必须真的落盘——返回 uuid 但磁盘没变等于没学。"""
    g, store, d = _make(None, [_write_call(), AIMessage(content="记下了")])
    cfg = {"configurable": {"thread_id": "t1"}}
    before = _ego_len(d / "kg.json")

    g.invoke({"messages": [{"role": "user", "content": "我开始学吉他了"}]}, cfg)
    g.invoke(Command(resume="approved_kg"), cfg)

    assert _ego_len(d / "kg.json") == before + 1, "批准后应新增一条"


def test_rejected_write_does_not_persist():
    """拒绝就不能写——HITL 的意义正在于此。"""
    g, store, d = _make(None, [_write_call(), AIMessage(content="好的，不记")])
    cfg = {"configurable": {"thread_id": "t2"}}
    before = _ego_len(d / "kg.json")

    g.invoke({"messages": [{"role": "user", "content": "我开始学吉他了"}]}, cfg)
    g.invoke(Command(resume="rejected"), cfg)

    assert _ego_len(d / "kg.json") == before, "拒绝后不应写入"


def test_log_mode_does_not_touch_kg():
    """只记日志不写图谱。"""
    g, store, d = _make(None, [_write_call(), AIMessage(content="记到日志")])
    cfg = {"configurable": {"thread_id": "t3"}}
    before = _ego_len(d / "kg.json")

    g.invoke({"messages": [{"role": "user", "content": "我开始学吉他了"}]}, cfg)
    g.invoke(Command(resume="approved_log"), cfg)

    assert _ego_len(d / "kg.json") == before


def test_learned_fact_is_retrievable_in_new_session():
    """核心：学过的东西，全新会话必须能检索到。"""
    g, store, d = _make(None, [_write_call(), AIMessage(content="记下了")])
    c1 = {"configurable": {"thread_id": "sess-a"}}
    g.invoke({"messages": [{"role": "user", "content": "我开始学吉他了"}]}, c1)
    g.invoke(Command(resume="approved_kg"), c1)

    hits = store.retrieve("吉他")
    assert hits, "学过的吉他必须能被检索到"
    assert any("吉他" in json.dumps(h, ensure_ascii=False) for h in hits)


def test_learned_node_has_source_trust():
    """对话中学来的，来源须标为 conversation（BC-011 的默认值）。"""
    g, store, d = _make(None, [_write_call(), AIMessage(content="记下了")])
    c1 = {"configurable": {"thread_id": "sess-b"}}
    g.invoke({"messages": [{"role": "user", "content": "我开始学吉他了"}]}, c1)
    g.invoke(Command(resume="approved_kg"), c1)

    # 注意：retrieve() 返回的是精简摘要，不含 source_trust，
    # 所以这里直接查 KG 里的完整节点。
    node = None
    for lst in store._kg["nodes"]["Cyber_Minghan"].values():
        if isinstance(lst, list):
            for n in lst:
                if n.get("event_label") == "开始学吉他":
                    node = n
                    break
        if node:
            break
    assert node is not None, "应能找到刚写入的节点"
    assert node.get("source_trust") == "conversation"
