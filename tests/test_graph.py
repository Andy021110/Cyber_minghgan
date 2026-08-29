"""
tests/test_graph.py — LangGraph 编排测试（FakeChatModel，零 API 调用）

覆盖：
- 纯文本回复 → persist → L0 落盘
- 读工具闭环（retrieve → 回 LLM → 回答）
- 写工具 → interrupt 暂停 → resume 三档语义（approved_kg / approved_log / rejected）
- 短期记忆压缩（compact 单元）
- thread 隔离（checkpointer）
"""


import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from agent.graph import build_graph, compose_system
from agent.memory import build_compact_messages, compact
from agent.models import FakeChatModel
from agent.state import new_turn
from cyber_planner import CyberBrainStore
from memory.episodic_store import EpisodicStore


def _new_node(label="测试节点", desc="用于测试的描述文本", evidence="证据里提到检索关键词"):
    return {
        "uuid": "a" * 32,
        "layer": "Ego",
        "event_label": label,
        "description": desc,
        "evidence": evidence,
        "batch_id": "Test",
        "round_refs": [],
        "created_at": "2026-08-29T00:00:00+00:00",
        "importance": 5,
        "access_count": 0,
        "last_accessed_at": None,
        "archived": False,
        "archived_at": None,
        "archive_reason": None,
        "source_mode": "test",
        "visibility": "private",
    }


def _seed_kg(tmp_env, node=None):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"])
    node = node or _new_node()
    store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"].append(dict(node))
    store._save()
    return store


@pytest.fixture
def env(tmp_env):
    store = _seed_kg(tmp_env)
    episodic = EpisodicStore(tmp_env["epi_path"])
    return {"tmp": tmp_env, "store": store, "episodic": episodic}


def _count_ego_nodes(store):
    return len(store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"])


def test_pure_text_reply_persists_to_l0(env):
    llm = FakeChatModel([AIMessage(content="我记得这事。")])
    g = build_graph(llm, env["store"], env["episodic"])

    out = g.invoke(new_turn("你还记得我喜欢什么吗"),
                   config={"configurable": {"thread_id": "t1"}})

    assert out["messages"][-1].content == "我记得这事。"
    assert env["episodic"].count() == 1
    assert "你还记得我喜欢什么吗" in env["episodic"].iter_all()[0].user_text


def test_read_tool_loop_returns_tool_result(env):
    call = AIMessage(
        content="",
        tool_calls=[{"name": "retrieve_memory", "args": {"keyword": "检索关键词"},
                     "id": "call_1"}],
    )
    llm = FakeChatModel([call, AIMessage(content="找到了。")])
    g = build_graph(llm, env["store"], env["episodic"])

    out = g.invoke(new_turn("你知道检索关键词吗"),
                   config={"configurable": {"thread_id": "t2"}})

    kinds = [type(m).__name__ for m in out["messages"]]
    assert "ToolMessage" in kinds
    assert out["messages"][-1].content == "找到了。"
    # 工具返回内容必须是 KG 里真实节点（证明检索链路真的走通，而不是空结果）
    tool_msgs = [m for m in out["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs and "测试节点" in str(tool_msgs[0].content)


def test_write_tool_interrupts_and_writes_on_approval(env):
    call = AIMessage(
        content="",
        tool_calls=[{
            "name": "create_memory",
            "args": {
                "layer": "Ego",
                "event_label": "新节点",
                "description": "这是一条通过审批写入的记忆",
                "evidence": "用户亲口说的",
            },
            "id": "call_w1",
        }],
    )
    llm = FakeChatModel([call, AIMessage(content="记下了。")])
    g = build_graph(llm, env["store"], env["episodic"])
    cfg = {"configurable": {"thread_id": "t3"}}

    before = _count_ego_nodes(env["store"])
    out = g.invoke(new_turn("帮我记住这件事"), config=cfg)

    # 1) 应当在 hitl_gate 处暂停
    interrupts = out.get("__interrupt__")
    assert interrupts, "写工具必须触发 interrupt"
    assert interrupts[0].value["writes"][0]["name"] == "create_memory"
    assert _count_ego_nodes(env["store"]) == before, "暂停期间不得写入"

    # 2) 批准后落库
    resumed = g.invoke(Command(resume="approved_kg"), config=cfg)
    assert _count_ego_nodes(env["store"]) == before + 1
    assert resumed["messages"][-1].content == "记下了。"


def test_write_tool_rejected_does_not_write(env):
    call = AIMessage(
        content="",
        tool_calls=[{
            "name": "create_memory",
            "args": {
                "layer": "Ego",
                "event_label": "不该写的",
                "description": "被拒绝的记忆",
                "evidence": "无",
            },
            "id": "call_w2",
        }],
    )
    llm = FakeChatModel([call, AIMessage(content="好的，不写。")])
    g = build_graph(llm, env["store"], env["episodic"])
    cfg = {"configurable": {"thread_id": "t4"}}
    before = _count_ego_nodes(env["store"])

    g.invoke(new_turn("记一下"), config=cfg)
    resumed = g.invoke(Command(resume="rejected"), config=cfg)

    assert _count_ego_nodes(env["store"]) == before, "rejected 不得写入图谱"
    tool_msgs = [m for m in resumed["messages"] if isinstance(m, ToolMessage)]
    assert any("拒绝" in str(m.content) for m in tool_msgs)


def test_approved_log_only_records(env):
    call = AIMessage(
        content="",
        tool_calls=[{
            "name": "create_memory",
            "args": {
                "layer": "Ego",
                "event_label": "只记日志",
                "description": "仅日志不入库",
                "evidence": "无",
            },
            "id": "call_w3",
        }],
    )
    llm = FakeChatModel([call, AIMessage(content="嗯，只记下来。")])
    g = build_graph(llm, env["store"], env["episodic"])
    cfg = {"configurable": {"thread_id": "t5"}}
    before = _count_ego_nodes(env["store"])

    g.invoke(new_turn("记一下"), config=cfg)
    resumed = g.invoke(Command(resume="approved_log"), config=cfg)

    assert _count_ego_nodes(env["store"]) == before
    tool_msgs = [m for m in resumed["messages"] if isinstance(m, ToolMessage)]
    assert any("未写入图谱" in str(m.content) for m in tool_msgs)


def test_compact_produces_summary_and_keeps_tail():
    from langchain_core.messages import HumanMessage

    msgs = [HumanMessage(content=f"第{i}轮内容") for i in range(10)]
    llm = FakeChatModel([AIMessage(content="合并后的摘要")])
    summary, kept = compact("", msgs, llm, keep_last=4)

    assert summary == "合并后的摘要"
    assert len(kept) == 4
    assert kept[-1].content == "第9轮内容"


def test_compact_falls_back_when_llm_fails():
    from langchain_core.messages import HumanMessage

    class _Boom:
        def invoke(self, messages, tools=None):
            raise RuntimeError("llm down")

    msgs = [HumanMessage(content=f"第{i}轮") for i in range(6)]
    summary, kept = compact("旧摘要", msgs, _Boom(), keep_last=2)
    assert "旧摘要" in summary
    assert len(kept) == 2


def test_compact_prompt_shape():
    from langchain_core.messages import HumanMessage

    msgs = [HumanMessage(content="你好"), AIMessage(content="在")]
    out = build_compact_messages("旧摘要", msgs)
    assert "旧摘要" in out[1].content
    assert "用户: 你好" in out[1].content


def test_thread_isolation(env):
    llm = FakeChatModel([AIMessage(content="A 线程"), AIMessage(content="B 线程")])
    g = build_graph(llm, env["store"], env["episodic"])

    g.invoke(new_turn("第一句"), config={"configurable": {"thread_id": "ta"}})
    out_b = g.invoke(new_turn("第二句"), config={"configurable": {"thread_id": "tb"}})

    # B 线程不应看到 A 线程的消息
    human_texts = [str(getattr(m, "content", ""))
                   for m in out_b["messages"] if getattr(m, "type", "") == "human"]
    assert "第二句" in human_texts
    assert "第一句" not in human_texts


def test_runner_builds_graph_without_touching_api(env, tmp_path):
    """runner 注入假 LLM 时应能组装图（不连 API、不写真实 KG）。"""
    from agent.runner import build_default_graph

    g = build_default_graph(
        kg_path=env["tmp"]["kg_path"],
        epi_path=env["tmp"]["epi_path"],
        checkpoint_db=str(tmp_path / "ckpt.db"),
        llm=FakeChatModel([AIMessage(content="组装成功")]),
    )
    out = g.invoke(new_turn("ping"), config={"configurable": {"thread_id": "r1"}})
    assert out["messages"][-1].content == "组装成功"


def test_sqlite_checkpointer_persists_across_graph_rebuilds(env, tmp_path):
    """短期记忆必须能跨重启续上：新图实例 + 同 thread_id 应读回既有状态。"""
    from agent.runner import build_sqlite_saver

    db = tmp_path / "ckpt.db"
    g1 = build_graph(FakeChatModel([AIMessage(content="第一轮")]),
                     env["store"], env["episodic"], checkpointer=build_sqlite_saver(db))
    g1.invoke(new_turn("第一句"), config={"configurable": {"thread_id": "persist"}})

    g2 = build_graph(FakeChatModel([AIMessage(content="第二轮")]),
                     env["store"], env["episodic"], checkpointer=build_sqlite_saver(db))
    snap = g2.get_state({"configurable": {"thread_id": "persist"}})
    assert snap.values["turn"] == 1
    assert "第一句" in str(snap.values["messages"][0].content)

    out = g2.invoke(new_turn("第二句"), config={"configurable": {"thread_id": "persist"}})
    assert out["turn"] == 2


def test_compose_system_includes_summary_and_retrieved():
    s = compose_system("人设", "前文摘要", "检索结果")
    assert "人设" in s and "前文摘要" in s and "检索结果" in s
