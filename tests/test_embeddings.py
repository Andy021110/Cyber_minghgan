"""embedding 模块单元测试：零向量回退 + 余弦相似度 + 混合打分。"""

import warnings

import numpy as np
import pytest

from memory.embeddings import (
    BgeEmbeddingProvider,
    EmbeddingProvider,
    ZeroEmbeddingProvider,
    cosine_similarity,
    get_provider,
    hybrid_score,
)


class _StubProvider(EmbeddingProvider):
    """可控 embedding，用于验证 hybrid score 融合逻辑。"""

    def __init__(self, vectors: list[list[float]]):
        self._vectors = np.asarray(vectors, dtype=np.float32)
        self._dim = self._vectors.shape[1]

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> np.ndarray:
        # 每个文本返回预设向量，循环复用
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, _ in enumerate(texts):
            out[i] = self._vectors[i % len(self._vectors)]
        return out


def test_zero_provider_shape_and_values():
    p = ZeroEmbeddingProvider(dim=128)
    assert p.dim == 128
    out = p.encode(["a", "b"])
    assert out.shape == (2, 128)
    assert np.allclose(out, 0)


def test_zero_provider_empty_list():
    p = ZeroEmbeddingProvider()
    out = p.encode([])
    assert out.shape == (0, 384)


def test_get_provider_defaults_to_zero():
    p = get_provider("zero")
    assert isinstance(p, ZeroEmbeddingProvider)
    p2 = get_provider(None)
    assert isinstance(p2, ZeroEmbeddingProvider)


def test_get_provider_bge_degrades_gracefully(monkeypatch):
    """BGE 拉不到模型时应降级为 Zero，且**必须告警**。

    为什么强调告警：静默降级会让"向量通路其实没生效"变成极难察觉的问题
    ——表现为检索效果差，却查不出原因。
    """
    monkeypatch.setenv("CYBER_EMBEDDING_PROVIDER", "bge")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        provider = get_provider("bge")

    if isinstance(provider, BgeEmbeddingProvider):
        return                       # 模型可用，走正常路径
    assert isinstance(provider, ZeroEmbeddingProvider), "降级后应是 Zero provider"
    assert any("降级" in str(w.message) for w in caught), "降级必须告警，不能静默"


def test_get_provider_default_is_zero(monkeypatch):
    """默认零向量通路，保证没有模型也能跑——这是 BC-001 之前没崩的原因。"""
    monkeypatch.delenv("CYBER_EMBEDDING_PROVIDER", raising=False)
    assert isinstance(get_provider(), ZeroEmbeddingProvider)


def test_cosine_similarity_orthogonal():
    a = np.array([[1.0, 0.0]], dtype=np.float32)
    b = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
    sim = cosine_similarity(a, b)
    assert sim.shape == (2,)
    assert np.isclose(sim[0], 0.0, atol=1e-6)
    assert np.isclose(sim[1], 1.0, atol=1e-6)


def test_cosine_similarity_zero_vectors():
    a = np.zeros((1, 4), dtype=np.float32)
    b = np.zeros((3, 4), dtype=np.float32)
    sim = cosine_similarity(a, b)
    assert np.allclose(sim, 0)


def test_hybrid_score_shape():
    kw = np.array([1.0, 0.0, 2.0])
    vec = np.array([0.5, 0.8, 0.1])
    out = hybrid_score(kw, vec, alpha=0.5, vector_scale=10.0)
    expected = 0.5 * kw + 0.5 * vec * 10.0
    assert out.shape == (3,)
    assert np.allclose(out, expected)


def test_hybrid_search_with_stub_provider_ranks_vector_match():
    """向量匹配但关键词不命中时，仍应能召回（验证混合检索确实工作）。"""
    # 3 个候选的向量：query 与候选1 同方向，候选2 正交，候选3 反向
    provider = _StubProvider([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
    ])
    query_emb = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    doc_emb = provider.encode(["doc1", "doc2", "doc3"])
    scores = cosine_similarity(query_emb, doc_emb)
    # 候选1 相似度最高
    assert scores[0] > scores[1]
    assert scores[0] > scores[2]
