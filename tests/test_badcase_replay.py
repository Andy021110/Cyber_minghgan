"""Badcase 登记 + 回放机制的自身测试。

为什么需要这套测试：
回放器是「防回归」的工具，但它自己也会坏。如果判定矩阵写错，
REGRESSION 永远不触发，那整套机制就是摆设——而且坏得无声无息。
所以机制本身必须有测试守着。
"""
import json

import pytest

from evals import badcases, replay


# ---------- 登记校验 ----------

def test_add_case_generates_id_and_defaults(tmp_path):
    p = tmp_path / "cases.jsonl"
    case = badcases.add_case(
        {"type": "retrieval", "title": "t",
         "reproduce": {"seed": [], "query": "q", "must_contain": "x"}},
        path=p,
    )
    assert case["id"] == "BC-001"
    assert case["status"] == "open"
    assert case["found_at"]           # 自动补日期


def test_reject_unknown_type(tmp_path):
    with pytest.raises(ValueError, match="type 必须是"):
        badcases.add_case({"type": "nonsense", "title": "t"}, path=tmp_path / "c.jsonl")


def test_reject_unknown_status(tmp_path):
    with pytest.raises(ValueError, match="status 必须是"):
        badcases.add_case(
            {"type": "infra", "title": "t", "status": "maybe"},
            path=tmp_path / "c.jsonl",
        )


@pytest.mark.parametrize("missing", ["seed", "query"])
def test_retrieval_requires_seed_and_query(tmp_path, missing):
    r = {"seed": [], "query": "q", "must_contain": "x"}
    r.pop(missing)
    with pytest.raises(ValueError, match=f"缺少 '{missing}'"):
        badcases.add_case(
            {"type": "retrieval", "title": "t", "reproduce": r},
            path=tmp_path / "c.jsonl",
        )


def test_retrieval_requires_expectation(tmp_path):
    """没有断言的 badcase 等于没登记——回放无从判定。"""
    with pytest.raises(ValueError, match="must_contain 或 must_not_contain"):
        badcases.add_case(
            {"type": "retrieval", "title": "t",
             "reproduce": {"seed": [], "query": "q"}},
            path=tmp_path / "c.jsonl",
        )


def test_load_skips_blank_and_comment_lines(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(
        "# 这是注释\n\n" + json.dumps({"id": "BC-001", "type": "infra"}) + "\n",
        encoding="utf-8",
    )
    assert len(badcases.load_cases(p)) == 1


def test_list_open_filters(tmp_path):
    p = tmp_path / "c.jsonl"
    badcases.save_cases(
        [{"id": "A", "type": "infra", "status": "open"},
         {"id": "B", "type": "infra", "status": "fixed"}], p)
    assert [c["id"] for c in badcases.list_open(p)] == ["A"]


def test_update_status_records_regression_test(tmp_path):
    p = tmp_path / "c.jsonl"
    badcases.save_cases([{"id": "A", "type": "infra", "status": "open"}], p)
    c = badcases.update_status("A", "fixed",
                               regression_test="tests/test_smoke.py", path=p)
    assert c["status"] == "fixed"
    assert c["regression_test"] == "tests/test_smoke.py"


# ---------- 判定矩阵 ----------

def _case(status, type_="retrieval", **kw):
    c = {"id": "X", "type": type_, "status": status, "title": "t"}
    c.update(kw)
    return c


PASS_R = {"source": "l0", "seed": [{"ts": "2026-01-01", "user_text": "我喝美式",
                                    "assistant_text": "记住了"}],
          "query": "美式", "must_contain": "美式"}
FAIL_R = {"source": "l0", "seed": [{"ts": "2026-01-01", "user_text": "我喝美式",
                                    "assistant_text": "记住了"}],
          "query": "美式", "must_contain": "拿铁"}


def test_verdict_fixed_and_pass_is_ok():
    row = replay.evaluate([_case("fixed", reproduce=PASS_R)])[0]
    assert (row["replay"], row["verdict"]) == ("pass", "OK")


def test_verdict_fixed_and_fail_is_regression():
    """本工具存在的核心理由：已修复的缺陷又坏了，必须被抓出来。"""
    row = replay.evaluate([_case("fixed", reproduce=FAIL_R)])[0]
    assert (row["replay"], row["verdict"]) == ("fail", "REGRESSION")


def test_verdict_open_and_fail_is_open():
    row = replay.evaluate([_case("open", reproduce=FAIL_R)])[0]
    assert (row["replay"], row["verdict"]) == ("fail", "OPEN")


def test_verdict_open_and_pass_is_recheck():
    """标着未修却能过：要么自愈了，要么当初记录不准，都要人看一眼。"""
    row = replay.evaluate([_case("open", reproduce=PASS_R)])[0]
    assert (row["replay"], row["verdict"]) == ("pass", "RECHECK")


def test_verdict_no_evidence_is_manual():
    row = replay.evaluate([_case("fixed", type_="infra")])[0]
    assert (row["replay"], row["verdict"]) == ("manual", "MANUAL")


def test_must_not_contain_semantics():
    """泄漏类缺陷用 must_not_contain：命中即为失败。"""
    r = {"source": "l0", "seed": [{"ts": "2026-01-01", "user_text": "私密内容",
                                   "assistant_text": "嗯"}],
         "query": "私密", "must_not_contain": "私密内容"}
    row = replay.evaluate([_case("open", reproduce=r)])[0]
    assert row["replay"] == "fail"          # 泄漏了 → 缺陷仍在


def test_replay_exception_is_surfaced_not_swallowed():
    """回放出错不能静默成 manual，否则缺陷会伪装成「无需验证」。"""
    row = replay.evaluate([_case("open", reproduce={"source": "l0"})])[0]
    assert row["replay"] == "fail"
    assert "回放异常" in row["detail"]


# ---------- 端到端 ----------

def test_main_returns_1_on_regression(tmp_path, capsys):
    """退出码 1 是给 CI 用的门禁；丢了它，无人值守就成了无人把关。"""
    p = tmp_path / "c.jsonl"
    badcases.save_cases(
        [{"id": "BC-001", "type": "retrieval", "status": "fixed",
          "title": "注入的坏样本", "reproduce": FAIL_R}], p)
    rc = replay.main(["--path", str(p)])
    assert rc == 1
    assert "REGRESSION" in capsys.readouterr().out


def test_main_returns_0_when_healthy(tmp_path, capsys):
    p = tmp_path / "c.jsonl"
    badcases.save_cases(
        [{"id": "BC-001", "type": "retrieval", "status": "fixed",
          "title": "守住的样本", "reproduce": PASS_R}], p)
    assert replay.main(["--path", str(p)]) == 0


def test_json_output_includes_coverage(tmp_path, capsys):
    """覆盖率报出来，是为了让「没检查」不伪装成「没回归」。"""
    p = tmp_path / "c.jsonl"
    badcases.save_cases(
        [{"id": "A", "type": "retrieval", "status": "fixed",
          "title": "自动", "reproduce": PASS_R},
         {"id": "B", "type": "infra", "status": "fixed", "title": "人工"}], p)
    replay.main(["--path", str(p), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["auto_verified"] == 1
    assert data["manual"] == 1
    assert data["coverage"] == pytest.approx(0.5)


def test_real_cases_file_is_loadable_and_wellformed():
    """守真实数据：cases.jsonl 必须能被解析，且 fixed 类都登记了回归测试。"""
    cases = badcases.load_cases()
    assert cases, "cases.jsonl 为空——badcase 登记处没生效"
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "badcase id 重复"
    for c in cases:
        if c.get("status") == "fixed":
            assert c.get("regression_test"), (
                f"{c['id']} 标记为 fixed 却没有回归测试——等于没修"
            )
