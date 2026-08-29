"""
embedding.py — 本地 embedding 抽象层（Phase 2）

设计：
- EmbeddingProvider：统一接口，dim + encode(texts) -> ndarray。
- ZeroEmbeddingProvider：无模型时回退，测试/CI 零依赖，输出全零向量。
- BgeEmbeddingProvider：本地加载 BAAI/bge-small-zh-v1.5，首次会从 HuggingFace 下载。
- get_provider()：通过环境变量 CYBER_EMBEDDING_PROVIDER 选择实现；默认 zero，
  避免在测试或数据准备阶段意外拉取大模型。

集成：
- EpisodicStore 与 CyberBrainStore 接收可选 provider，做 keyword + vector 混合检索。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

import numpy as np


class EmbeddingProvider(ABC):
    """Embedding 抽象接口。"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度。"""
        ...

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """对文本列表进行编码，返回 (n_texts, dim) 的 float32 ndarray。"""
        ...


class ZeroEmbeddingProvider(EmbeddingProvider):
    """
    零向量占位实现。用于：
    - 测试环境（不下载模型、确定性输出）
    - 未启用向量检索时的默认回退
    """

    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        return np.zeros((len(texts), self._dim), dtype=np.float32)


class BgeEmbeddingProvider(EmbeddingProvider):
    """
    本地 BGE 中文 embedding（默认 bge-small-zh-v1.5）。

    依赖：sentence-transformers
    安装：pip install sentence-transformers

    首次使用会从 HuggingFace Hub 下载模型（约 100MB）。
    可通过 env CYBER_EMBEDDING_MODEL 覆盖模型名。
    """

    DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"

    def __init__(
        self,
        model_name: str | None = None,
        device: str = "cpu",
        cache_dir: str | None = None,
    ):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "BgeEmbeddingProvider 需要 sentence-transformers。\n"
                "请安装：pip install sentence-transformers\n"
                "或改用 ZeroEmbeddingProvider。"
            ) from exc

        model_name = model_name or os.environ.get("CYBER_EMBEDDING_MODEL", self.DEFAULT_MODEL)
        kwargs = {"device": device}
        if cache_dir:
            kwargs["cache_folder"] = cache_dir
        self.model = SentenceTransformer(model_name, **kwargs)
        self._dim = self.model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        # normalize=True 保证 cosine 等价于 dot product
        return np.asarray(
            self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )


def get_provider(name: str | None = None) -> EmbeddingProvider:
    """
    工厂函数。

    name 可选值：
    - "bge" -> BgeEmbeddingProvider
    - "zero" / 未设置 -> ZeroEmbeddingProvider
    """
    name = (name or os.environ.get("CYBER_EMBEDDING_PROVIDER", "zero")).lower()
    if name == "bge":
        try:
            return BgeEmbeddingProvider()
        except Exception as exc:
            # 模型拉不到（huggingface.co 与 hf-mirror 在本环境均不可达，已实测）
            # 时降级，而不是让整个检索挂掉——关键词通路仍可工作。
            # 但**不能静默降级**：否则"向量通路其实没生效"会变成极难察觉的问题
            # （表现为检索效果差却查不出原因）。所以必须告警。
            import warnings

            warnings.warn(
                f"BGE 不可用，降级为 Zero provider（向量通路不参与）：{exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return ZeroEmbeddingProvider()
    return ZeroEmbeddingProvider()


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2 归一化，避免除零。"""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    # 全零向量保持为零，后续 cosine 会处理为 0
    return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 1e-12)


def cosine_similarity(query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    """
    计算 query 与 docs 的余弦相似度。
    输入需已 L2 归一化；若未归一化则内部先归一化。
    """
    query_vec = _normalize(np.asarray(query_vec, dtype=np.float32).reshape(1, -1))
    doc_vecs = _normalize(np.asarray(doc_vecs, dtype=np.float32))
    if doc_vecs.shape[0] == 0:
        return np.zeros((0,), dtype=np.float32)
    sim = np.dot(doc_vecs, query_vec.T).squeeze(-1)
    # 全零向量之间的相似度为 nan，替换为 0（不参与排序）
    return np.nan_to_num(sim, nan=0.0, posinf=0.0, neginf=0.0)


def hybrid_score(
    keyword_scores: np.ndarray,
    vector_scores: np.ndarray,
    alpha: float = 0.5,
    vector_scale: float = 10.0,
) -> np.ndarray:
    """
    融合 keyword score 与 vector score。

    - alpha：向量部分权重（0 纯关键词，1 纯向量）。
    - vector_scale：把 cosine [0,1] 放大到与 keyword score 同量级。
    """
    keyword = np.asarray(keyword_scores, dtype=np.float32)
    vector = np.asarray(vector_scores, dtype=np.float32)
    return (1 - alpha) * keyword + alpha * vector * vector_scale
