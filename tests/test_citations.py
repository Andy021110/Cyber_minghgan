"""引用校验（A2 / 压幻觉）的测试。

定位是「可信的个人代理」，最大的敌人不是检索不到，而是**编**。
竞品在这上面栽得很彻底：LongMemEval 专门设 Abstention 类别测
"该说不知道时会不会编"，MemFail 里 52.3% 的查询是误导性的，
系统却拿无关实体的档案作答。

本模块只校验**引用合法性**，不校验事实正确性——
引用合法但内容失真（过度概括）是另一个问题，不要用这个指标假装覆盖了。
"""
from agent.citations import extract_citations, short_uuid, validate_citations
from agent.memory import _format_l1, _format_l0


def test_extract_citations_deduplicates():
    text = "根据 [ref:abc12345] 与 [ref:abc12345] 还有 [ref:def67890]"
    assert extract_citations(text) == ["abc12345", "def67890"]


def test_extract_citations_empty_when_absent():
    assert extract_citations("没有任何引用的一句话") == []


def test_legal_citation_passes():
    res = validate_citations("依据 [ref:abc12345] 可知", {"abc12345"})
    assert res["ok"] is True
    assert res["illegal"] == []


def test_fabricated_citation_is_caught():
    """核心用例：引用了本次检索之外的 id = 幻觉，必须拦下。"""
    res = validate_citations("依据 [ref:deadbeef] 可知", {"abc12345"})
    assert res["ok"] is False
    assert res["illegal"] == ["deadbeef"]


def test_short_ref_matches_full_uuid_by_prefix():
    """注入 prompt 用 8 位短 uuid，校验时要能匹配完整 uuid。"""
    full = "abc12345-6789-4def-8abc-1234567890ab"
    res = validate_citations("见 [ref:abc12345]", {full})
    assert res["ok"] is True
    assert short_uuid(full) == "abc12345"


def test_uncited_reports_unused_but_is_not_an_error():
    """检索到却没引用不算错，只提示——强制全引用会导致硬凑引用。"""
    res = validate_citations("见 [ref:aaaa]", {"aaaa", "bbbb"})
    assert res["ok"] is True
    assert res["uncited"] == ["bbbb"]


def test_ids_shorter_than_4_chars_are_ignored():
    """低于 4 字符不做引用解析——否则日常文本里的括号会被误判成引用。"""
    assert extract_citations("见 [ref:ab] 与 [ref:abcd]") == ["abcd"]


def test_l0_eid_style_ref_is_supported():
    """L0 用 eid（含下划线），不能被正则漏掉。"""
    res = validate_citations("那次 [ref:ep_2026-03-11_0000] 说过",
                             {"ep_2026-03-11_0000"})
    assert res["ok"] is True


# ── prompt 必须带上引用标识，否则 LLM 无从引用 ──

def test_format_l1_includes_ref():
    """A2 的前提：uuid 必须出现在注入 prompt 里。"""
    hits = [{"uuid": "abcdef12-3456", "layer": "Ego",
             "event_label": "某节点", "description": "描述"}]
    out = _format_l1(hits)
    assert "[ref:abcdef12]" in out


def test_format_l0_includes_ref():
    hits = [{"eid": "ep_2026-01-01_0000", "ts": "2026-01-01",
             "user_text": "你好", "assistant_text": "嗨"}]
    assert "[ref:ep_2026-01-01_0000]" in _format_l0(hits)


def test_empty_hits_yield_empty_string():
    assert _format_l1([]) == ""
    assert _format_l0([]) == ""
