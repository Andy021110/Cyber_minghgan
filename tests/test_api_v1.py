"""
tests/test_api_v1.py — v1 API 集成测试（TestClient + FakeChatModel，零 API）

验证 LangGraph 编排层通过 HTTP 暴露后的完整链路：
发消息 → （写记忆时）中断 → 审批恢复 → 短期记忆快照可读。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent.graph import build_graph
from agent.models import FakeChatModel
from api import deps
from api.routes import v1
from cyber_planner import CyberBrainStore
from memory.episodic_store import EpisodicStore


def _seed_kg(tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    return store


def _make_client(graph) -> TestClient:
    app = FastAPI()
    app.include_router(v1.router, prefix="/api/v1")
    app.dependency_overrides[deps.get_graph] = lambda: graph
    return TestClient(app)


@pytest.fixture
def env(tmp_env):
    return {
        "tmp": tmp_env,
        "store": _seed_kg(tmp_env),
        "episodic": EpisodicStore(tmp_env["epi_path"]),
    }


def test_chat_plain_reply(env):
    llm = FakeChatModel([AIMessage(content="我记得。")])
    client = _make_client(build_graph(llm, env["store"], env["episodic"]))

    r = client.post("/api/v1/chat", json={"thread_id": "api1", "message": "你好"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "我记得。"
    assert body["interrupted"] is False


def test_chat_interrupt_then_resume_writes_kg(env):
    call = AIMessage(
        content="",
        tool_calls=[{
            "name": "create_memory",
            "args": {
                "layer": "Ego",
                "event_label": "API 写入",
                "description": "通过 API 审批写入的记忆",
                "evidence": "用户说要记住",
            },
            "id": "call_api1",
        }],
    )
    llm = FakeChatModel([call, AIMessage(content="记下了。")])
    graph = build_graph(llm, env["store"], env["episodic"])
    client = _make_client(graph)

    before = len(env["store"]._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"])

    r1 = client.post("/api/v1/chat", json={"thread_id": "api2", "message": "记一下这件事"})
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["interrupted"] is True
    assert b1["interrupts"][0]["value"]["writes"][0]["name"] == "create_memory"
    assert len(env["store"]._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]) == before

    r2 = client.post("/api/v1/chat/resume",
                     json={"thread_id": "api2", "decision": "approved_kg"})
    assert r2.status_code == 200
    assert r2.json()["reply"] == "记下了。"
    assert len(env["store"]._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"]) == before + 1


def test_memory_snapshot_endpoint(env):
    llm = FakeChatModel([AIMessage(content="好。")])
    client = _make_client(build_graph(llm, env["store"], env["episodic"]))

    client.post("/api/v1/chat", json={"thread_id": "api3", "message": "第一句"})
    r = client.get("/api/v1/memory/api3")
    assert r.status_code == 200
    body = r.json()
    assert body["thread_id"] == "api3"
    assert body["turn"] == 1
    assert body["message_count"] >= 2  # human + ai


def test_memory_snapshot_404_for_unknown_thread(env):
    llm = FakeChatModel([])
    client = _make_client(build_graph(llm, env["store"], env["episodic"]))
    r = client.get("/api/v1/memory/nonexistent")
    assert r.status_code == 404
