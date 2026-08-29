"""冒烟测试：验证 Mock LLM 基建本身可用（不调 API）。"""
from conftest import FakeAnthropic, FakeResponse, text_block, tool_use_block


def test_fake_client_default_response(fake_client):
    resp = fake_client.messages.create(model="x", messages=[{"role": "user", "content": "hi"}])
    assert resp.stop_reason == "end_turn"
    assert resp.content[0].type == "text"
    assert fake_client.messages.call_count == 1


def test_scripted_tool_use_flow():
    client = FakeAnthropic(script=[
        FakeResponse([tool_use_block("t1", "retrieve", keyword="memory")], stop_reason="tool_use"),
        FakeResponse([text_block("结果来了")]),
    ])
    r1 = client.messages.create(messages=[])
    assert r1.stop_reason == "tool_use"
    assert r1.content[0].name == "retrieve"
    assert r1.content[0].input["keyword"] == "memory"
    r2 = client.messages.create(messages=[])
    assert r2.content[0].text == "结果来了"
    assert client.messages.call_count == 2


def test_script_callable_step():
    """脚本步骤可以是函数：根据请求参数动态出响应。"""
    def step(kwargs):
        tools = kwargs.get("tools") or []
        return FakeResponse(
            [text_block(f"收到 {len(tools)} 个工具定义，模型={kwargs.get('model')}")]
        )
    client = FakeAnthropic(script=[step])
    resp = client.messages.create(model="deepseek-v4-pro", tools=[{"name": "x"}])
    assert "1 个工具定义" in resp.content[0].text
