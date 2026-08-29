"""实验台账自身的测试。

台账的意义是「让探索不原地打转」，所以它自己必须靠得住：
假设不许空、指标不许空、结论取值受限、差值算得对。
"""
import json

import pytest

from experiments import ledger


def _fresh(tmp_path):
    return tmp_path / "ledger.jsonl"


def test_propose_requires_hypothesis(tmp_path):
    """说不清在验证什么就别做——这是防「假实验」的第一道闸。"""
    with pytest.raises(ValueError, match="hypothesis 不能为空"):
        ledger.propose(hypothesis="  ", change="c", metric="m", path=_fresh(tmp_path))


def test_propose_requires_metric(tmp_path):
    with pytest.raises(ValueError, match="metric 不能为空"):
        ledger.propose(
            hypothesis="h", change="c", metric="", path=_fresh(tmp_path))


def test_propose_creates_running_experiment(tmp_path):
    p = _fresh(tmp_path)
    exp = ledger.propose(
        hypothesis="提高 λ 能提升召回", change="λ 0.4→0.6",
        metric="Recall@5", baseline=0.62, path=p)
    assert exp["id"] == "EXP-001"
    assert exp["status"] == "running"
    assert exp["result"] is None
    assert exp["decision"] is None


def test_ids_increment(tmp_path):
    p = _fresh(tmp_path)
    for i in range(3):
        e = ledger.propose(hypothesis=f"h{i}", change="c", metric="m", path=p)
    assert e["id"] == "EXP-003"


def test_conclude_computes_delta(tmp_path):
    p = _fresh(tmp_path)
    exp = ledger.propose(hypothesis="h", change="c", metric="Recall@5",
                         baseline=0.62, path=p)
    done = ledger.conclude(exp["id"], result=0.71, decision="adopt", path=p)
    assert done["delta"] == pytest.approx(0.09)
    assert done["status"] == "done"


def test_conclude_non_numeric_delta_is_none(tmp_path):
    """通过/不通过这类结果不该硬凑出数字差值。"""
    p = _fresh(tmp_path)
    exp = ledger.propose(hypothesis="h", change="c", metric="是否崩溃",
                         baseline="崩溃", path=p)
    done = ledger.conclude(exp["id"], result="未崩溃", decision="adopt", path=p)
    assert done["delta"] is None


def test_conclude_rejects_bad_decision(tmp_path):
    p = _fresh(tmp_path)
    exp = ledger.propose(hypothesis="h", change="c", metric="m", path=p)
    with pytest.raises(ValueError, match="decision 必须是"):
        ledger.conclude(exp["id"], result=1, decision="looks-good", path=p)


def test_conclude_unknown_id_raises(tmp_path):
    with pytest.raises(KeyError):
        ledger.conclude("EXP-999", result=1, decision="adopt", path=_fresh(tmp_path))


def test_stats_adoption_rate(tmp_path):
    p = _fresh(tmp_path)
    a = ledger.propose(hypothesis="h", change="c", metric="m", path=p)
    ledger.conclude(a["id"], 1, "adopt", path=p)
    b = ledger.propose(hypothesis="h", change="c", metric="m", path=p)
    ledger.conclude(b["id"], 1, "reject", path=p)
    ledger.propose(hypothesis="h", change="c", metric="m", path=p)  # 仍在进行
    s = ledger.stats(p)
    assert (s["total"], s["done"], s["running"]) == (3, 2, 1)
    assert s["adopted"] == 1 and s["rejected"] == 1
    assert s["adoption_rate"] == pytest.approx(0.5)


def test_stats_empty_ledger_is_safe(tmp_path):
    """台账还没建时不能炸——它是要被 CI 和日常脚本随时调用的。"""
    s = ledger.stats(tmp_path / "does-not-exist.jsonl")
    assert s["total"] == 0
    assert s["adoption_rate"] == 0.0


def test_load_skips_garbage_lines(tmp_path):
    p = _fresh(tmp_path)
    p.write_text("# 注释\n{bad json\n" + json.dumps({"id": "EXP-001"}) + "\n",
                 encoding="utf-8")
    assert len(ledger.load(p)) == 1


def test_show_renders_rows(tmp_path):
    p = _fresh(tmp_path)
    e = ledger.propose(hypothesis="h", change="λ 0.4→0.6", metric="Recall@5",
                       baseline=0.62, path=p)
    ledger.conclude(e["id"], 0.71, "adopt", path=p)
    out = ledger.show(path=p)
    assert "EXP-001" in out and "Recall@5" in out and "adopt" in out
