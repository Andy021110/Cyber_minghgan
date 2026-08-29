"""
tests/test_retrieval_ab.py — 检索 A/B 评测骨架测试（合成数据，零依赖零 API）

目的：保证指标定义与入库/映射链路正确。
真实跑分需要下载 LongMemEval 数据集（仓库不收录），不在 CI 里跑。
"""

import pytest

from evals.retrieval_ab import (
    evaluate_arm,
    ingest_item,
    load_items,
    mrr_at_k,
    recall_at_k,
    run_ab,
)
from memory.embeddings import ZeroEmbeddingProvider


def _item(qid="q1", question="美式", gold=("s1",)):
    return {
        "question_id": qid,
        "question_type": "single-session-user",
        "question": question,
        "haystack_session_ids": ["s1", "s2"],
        "haystack_dates": ["2026/01/01", "2026/02/01"],
        "haystack_sessions": [
            [
                {"role": "user", "content": "我平时只喝美式"},
                {"role": "assistant", "content": "记住了"},
            ],
            [
                {"role": "user", "content": "今天天气不错"},
                {"role": "assistant", "content": "是的"},
            ],
        ],
        "answer_session_ids": list(gold),
    }


def test_recall_at_k_basic():
    assert recall_at_k(["s1", "s2"], {"s1"}, k=5) == 1.0
    assert recall_at_k(["s2", "s1"], {"s1"}, k=5) == 1.0
    assert recall_at_k(["s2", "s3"], {"s1"}, k=5) == 0.0
    # k 之外命中不算
    assert recall_at_k(["s2", "s3", "s1"], {"s1"}, k=2) == 0.0


def test_recall_at_k_empty_gold_is_zero():
    """gold 缺失必须记 0，绝不能静默算满分——否则评测会虚高。"""
    assert recall_at_k(["s1"], set(), k=5) == 0.0


def test_mrr_at_k():
    assert mrr_at_k(["s1"], {"s1"}, k=5) == 1.0
    assert mrr_at_k(["s2", "s3", "s1"], {"s1"}, k=5) == pytest.approx(1 / 3)
    assert mrr_at_k(["s2"], {"s1"}, k=5) == 0.0


def test_run_ab_with_zero_provider_shows_no_gain():
    """Zero provider 下两组必然同分——防止有人拿空跑结果宣称『混合检索有效』。"""
    result = run_ab([_item()], k=5, limit=1)
    assert result["delta_recall"] == 0.0
    assert result["baseline_keyword_only"]["recall_at_k"] == 1.0


def test_evaluate_arm_recalls_gold_session():
    arm = evaluate_arm([_item()], ZeroEmbeddingProvider(), k=5, alpha=0.0)
    assert arm["n"] == 1
    assert arm["recall_at_k"] == 1.0
    assert arm["mrr_at_k"] == 1.0


def test_evaluate_arm_miss_when_question_terms_absent():
    """问题关键词不在原文里时召回为 0 —— 这正是向量检索要补的短板。"""
    arm = evaluate_arm([_item(question="手冲")], ZeroEmbeddingProvider(), k=5, alpha=0.0)
    assert arm["recall_at_k"] == 0.0


def test_ingest_maps_episode_to_session_id(tmp_path):
    from memory.episodic_store import EpisodicStore

    epi = EpisodicStore(tmp_path / "epi.jsonl")
    eid2sid = ingest_item(epi, _item())
    assert epi.count() >= 2
    assert set(eid2sid.values()) == {"s1", "s2"}
    # 含「美式」的 episode 应映射到 s1
    hits = epi.search("美式", limit=5)
    assert hits and eid2sid[hits[0]["eid"]] == "s1"


def test_load_items_raises_with_guidance(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        load_items(str(tmp_path / "nope.json"))
    assert "数据集来源与下载说明" in str(exc.value)
