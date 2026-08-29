"""pytest 共享基建：FakeAnthropic（Mock LLM）+ 临时环境隔离。

设计：
- FakeAnthropic 替换真实 client，messages.create 返回脚本化响应（属性访问兼容，
  与代码里 block.type / block.id / block.input 一致），测试不烧 API、可进 CI。
- tmp_env 用临时目录隔离 KG / L0 / 日志，绝不碰真实数据。
- 所有 LLM 调用被记录（client.messages.calls），供断言「调了几次、传了什么」。
"""
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

# 项目根目录入 sys.path（与 api/main.py 同款做法，但集中在此）
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "pipelines"))

# ── 响应块构造 ──────────────────────────────────────────────

def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def tool_use_block(tool_id: str, name: str, **input_) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=input_)


def tool_result_block(tool_use_id: str, content: str) -> SimpleNamespace:
    return SimpleNamespace(type="tool_result", tool_use_id=tool_use_id, content=content)


class _Usage(SimpleNamespace):
    input_tokens = 10
    output_tokens = 10


class FakeResponse:
    """模拟 anthropic 响应：content 是 block 列表，stop_reason 决定流程走向。"""

    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = _Usage()


class FakeMessages:
    """模拟 client.messages：按脚本（script）顺序出响应，记录所有调用。"""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.script:
            step = self.script.pop(0)
            if callable(step):
                return step(kwargs)
            return step
        return FakeResponse([text_block("（mock 默认响应）")])

    @property
    def call_count(self) -> int:
        return len(self.calls)


class FakeAnthropic:
    """测试用假 client：结构对齐 anthropic.Anthropic。"""

    def __init__(self, script=None):
        self.messages = FakeMessages(script)


# ── fixtures ────────────────────────────────────────────────

@pytest.fixture
def fake_client():
    """返回 FakeAnthropic 实例，测试结束后可查 client.messages.calls。"""
    return FakeAnthropic()


@pytest.fixture
def scripted_client():
    """返回 (client, set_script) —— 可随时替换后续响应脚本。"""
    client = FakeAnthropic()
    return client, client.messages.script


@pytest.fixture
def tmp_env():
    """临时环境：拷贝真实 KG 作为测试基线 + 空 L0/日志目录，不污染真实数据。

    yield dict: {root, kg_path, persona_path, logs_dir, epi_path}
    """
    root = Path(tempfile.mkdtemp(prefix="cyber_test_"))
    src_kg = _ROOT / "yuanbao_cyber_minghan_kg.json"
    kg_path = root / "test_kg.json"
    shutil.copy(src_kg, kg_path)  # 真实结构，安全副本
    persona_path = root / "persona.md"
    persona_path.write_text("# 测试人格\n深度工作偏好。", encoding="utf-8")
    logs_dir = root / "decision_logs"
    logs_dir.mkdir()
    epi_dir = root / "memory" / "episodic"
    epi_dir.mkdir(parents=True)
    env = {
        "root": root,
        "kg_path": kg_path,
        "persona_path": persona_path,
        "logs_dir": logs_dir,
        "epi_path": epi_dir / "test.jsonl",
    }
    yield env
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def hitl_env(tmp_env, monkeypatch):
    """隔离 HITL 队列：把 decision_log 全部函数的 logs_dir 默认值绑到临时目录，
    并把 cyber_planner 的 HEALTH_LOG_PATH 也指过去——任何路径都不会碰真实数据。"""
    import functools

    import cyber_planner as cp
    import pipelines.decision_log as dl

    logs = tmp_env["logs_dir"]
    _HITL_FNS = [
        "write_pending", "read_pending", "count_pending", "update_pending_status",
        "write_approval_item", "read_awaiting", "resolve_approval",
        "write_notification", "read_notifications", "consume_notification",
    ]
    for name in _HITL_FNS:
        fn = getattr(dl, name, None)
        if fn is not None:
            monkeypatch.setattr(dl, name, functools.partial(fn, logs_dir=logs))
        if hasattr(cp, name):
            monkeypatch.setattr(cp, name, functools.partial(getattr(dl, name), logs_dir=logs))
    monkeypatch.setattr(cp, "HEALTH_LOG_PATH", logs / "health_log.jsonl")
    return logs
