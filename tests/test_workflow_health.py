"""工作流健康度指标的测试。

指标是用来做决策的：算错了，比不算更糟——
覆盖率算高会让人误以为「没回归」，实则是「没检查」。
"""
import pytest

from evals import health


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """所有测试都在临时台账/用例上进行，不碰仓库里的真实数据。"""
    cases = tmp_path / "cases.jsonl"
    led = tmp_path / "ledger.jsonl"
    cases.write_text("", encoding="utf-8")
    led.write_text("", encoding="utf-8")
    monkeypatch.setattr(health.badcases, "_DEFAULT_PATH", cases)
    monkeypatch.setattr(health.ledger, "_DEFAULT_PATH", led)
    return cases, led


def _write_cases(path, rows):
    import json
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


PASS_R = {"source": "l0", "seed": [{"ts": "2026-01-01", "user_text": "美式",
                                    "assistant_text": "好"}],
          "query": "美式", "must_contain": "美式"}


def test_empty_state_is_safe(_isolate):
    """空仓库不能除零崩掉。"""
    m = health.collect()
    assert m["badcase"]["coverage"] == 0.0
    assert m["experiment"]["adoption_rate"] == 0.0


def test_retention_counts_only_passing_fixed(_isolate):
    cases, _ = _isolate
    _write_cases(cases, [
        {"id": "A", "type": "retrieval", "status": "fixed", "title": "守住",
         "reproduce": PASS_R},
        {"id": "B", "type": "retrieval", "status": "fixed", "title": "回归了",
         "reproduce": {"source": "l0", "seed": [], "query": "q",
                       "must_contain": "不可能出现的字符串"}},
    ])
    m = health.collect()
    assert m["badcase"]["fixed"] == 2
    assert m["badcase"]["retention"] == 0.5
    assert m["badcase"]["regressions"] == ["B"]


def test_coverage_excludes_manual(_isolate):
    cases, _ = _isolate
    _write_cases(cases, [
        {"id": "A", "type": "retrieval", "status": "fixed", "title": "自动",
         "reproduce": PASS_R},
        {"id": "B", "type": "infra", "status": "fixed", "title": "人工"},
    ])
    m = health.collect()
    assert m["badcase"]["manual"] == 1
    assert m["badcase"]["coverage"] == pytest.approx(0.5)


def test_diagnose_flags_regression(_isolate):
    cases, _ = _isolate
    _write_cases(cases, [
        {"id": "A", "type": "retrieval", "status": "fixed", "title": "回归了",
         "reproduce": {"source": "l0", "seed": [], "query": "q",
                       "must_contain": "不可能出现的字符串"}},
    ])
    tips = health.diagnose(health.collect())
    assert any("回归" in t and "严重" in t for t in tips)


def test_diagnose_flags_low_coverage(_isolate):
    """覆盖率低必须被点出来，否则「无回归」是自欺。"""
    cases, _ = _isolate
    _write_cases(cases, [
        {"id": f"M{i}", "type": "infra", "status": "open", "title": "人工"}
        for i in range(4)
    ])
    tips = health.diagnose(health.collect())
    assert any("覆盖率" in t for t in tips)


def test_diagnose_clean_state(_isolate):
    assert "正常" in health.diagnose(health.collect())[0]
