"""EpisodicStore / CyberBrainStore 混合检索测试。

使用 StubEmbeddingProvider 替代真实模型，验证 keyword + vector 融合路径正确。
"""

import json

import numpy as np
import pytest

from cyber_planner import CyberBrainStore
from memory.embeddings import EmbeddingProvider
from memory.episodic_store import EpisodicStore


class _StubProvider(EmbeddingProvider):
    """字符袋（bag-of-chars）向量：文本含词表第 i 个字，则第 i 维置 1。

    为什么不用内置 hash()：Python 的字符串哈希逐进程随机（PYTHONHASHSEED），
    同一份代码在不同进程里会得到不同排序。早期版本正是因此变成 flaky test
    （本地跑过、换进程就挂），这里改用与进程无关的字符袋编码。
    """

    def __init__(self, vocab: str = "元宇宙发布会完全不同的内容"):
        self.vocab = list(vocab)

    @property
    def dim(self) -> int:
        return len(self.vocab)

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for j, ch in enumerate(self.vocab):
                if ch in t:
                    out[i, j] = 1.0
        return out


@pytest.fixture
def stub_provider():
    return _StubProvider()


def test_episodic_keyword_search_still_works(stub_provider, tmp_env):
    store = EpisodicStore(tmp_env["epi_path"], provider=stub_provider, vector_alpha=0.0)
    store.append(ts="2026-08-21", user_text="我喜欢喝咖啡", assistant_text="好的")
    store.append(ts="2026-08-22", user_text="我讨厌苦味", assistant_text="明白")

    hits = store.search("咖啡", limit=5)
    assert len(hits) == 1
    assert "咖啡" in hits[0]["user_text"]


def test_episodic_hybrid_vector_recalls_semantic_like_match(stub_provider, tmp_env):
    """关键词完全不命中，但向量完全匹配时，仍应召回（用 stub 模拟语义相似）。"""
    store = EpisodicStore(tmp_env["epi_path"], provider=stub_provider, vector_alpha=1.0)
    # 向量由文本 hash 决定，query 与 doc_text 完全相同 -> 相似度 1.0
    store.append(ts="2026-08-21", user_text="元宇宙发布会", assistant_text="ok")
    store.append(ts="2026-08-22", user_text="完全不同的内容", assistant_text="ok")

    hits = store.search("元宇宙发布会", limit=5)
    assert len(hits) == 2  # vector alpha=1，所有文档都会有一个 cosine 分数，stub 空间小会乱序但都有分
    # 最高分应为相同文本
    assert "元宇宙发布会" in hits[0]["user_text"]


def test_cyberbrain_keyword_retrieve_updates_access_metadata(stub_provider, tmp_env):
    store = CyberBrainStore(kg_path=tmp_env["kg_path"], provider=stub_provider, vector_alpha=0.0)
    # 真实 KG 中大概率存在 "猫" 或 "弓佳彤" 等关键词；这里用一个稳定的公开节点
    node = {
        "uuid": "deadbeefdeadbeefdeadbeefdeadbeef",
        "layer": "Ego",
        "event_label": "测试节点",
        "description": "用于测试检索的描述文本",
        "evidence": "证据里提到测试关键词",
        "batch_id": "Test",
        "round_refs": [],
        "created_at": "2026-08-21T00:00:00+00:00",
        "importance": 5,
        "access_count": 0,
        "last_accessed_at": None,
        "archived": False,
        "archived_at": None,
        "archive_reason": None,
        "source_mode": "test",
        "visibility": "private",
    }
    store._kg["nodes"]["Cyber_Minghan"]["Ego_Dynamics"].append(node)
    store._save()

    hits = store.retrieve("测试关键词", limit=10)
    assert any(h["uuid"] == node["uuid"] for h in hits)
    # 命中后应更新 access_count
    store2 = CyberBrainStore(kg_path=tmp_env["kg_path"], provider=stub_provider)
    found = store2._find_by_uuid(node["uuid"])
    assert found[0][found[1]]["access_count"] == 1
    assert found[0][found[1]]["last_accessed_at"] is not None


def test_cyberbrain_empty_kg_returns_empty(stub_provider, tmp_env):
    # 构造空 KG 结构
    kg_path = tmp_env["root"] / "empty_kg.json"
    kg_path.write_text(
        json.dumps({"nodes": {"Cyber_Minghan": {}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    store = CyberBrainStore(kg_path=kg_path, provider=stub_provider)
    assert store.retrieve("任意词") == []
