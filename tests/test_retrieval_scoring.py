"""检索打分（IDF 加权 2-gram）的回归测试。

背景：改造前 `retrieve` 用 `query in text` 整句布尔匹配。
中文不分词，整句作为子串在原文里几乎必然不存在，
叠加 sentence-transformers 未安装（vector_alpha 被强制 0），
实测 5 个自然问句 top5 命中 **0 条**——检索等于关闭（BC-001）。

这里守住两件事：能召回、以及**该弃权时弃权**。
后者同等重要：召回一堆不相关的记忆，比空手更糟。
"""
from cyber_planner import CyberBrainStore, keyword_score, keyword_scores_idf


def _store(tmp_env, **kw):
    return CyberBrainStore(kg_path=tmp_env["kg_path"], **kw)


# ── 打分函数本身 ──

def test_identical_text_scores_one():
    assert keyword_score("咖啡偏好", "咖啡偏好") == 1.0


def test_disjoint_text_scores_zero():
    assert keyword_score("咖啡偏好", "完全不同的内容") == 0.0


def test_punctuation_is_ignored():
    """问句带问号不影响匹配——这是整句匹配最常踩的坑。"""
    assert keyword_score("你喜欢咖啡吗？", "关于咖啡的偏好") > 0


def test_single_char_query_degrades_to_substring():
    assert keyword_score("猫", "养了一只猫") == 1.0
    assert keyword_score("猫", "没有宠物") == 0.0


def test_idf_downweights_common_fragments():
    """罕见片段应比高频片段得分高——否则「喜欢」会淹没「咖啡」。

    这条是不加权版本失效的直接原因：实测「他喜欢喝咖啡吗」在 KG 里
    根本没有咖啡内容，却因大量文档含「喜欢」而召回 5 条不相关记忆。
    """
    texts = ["我喜欢跑步", "我喜欢读书", "我喜欢爬山", "我喝咖啡"]
    coffee = keyword_scores_idf("咖啡", texts)
    like = keyword_scores_idf("喜欢", texts)
    assert max(coffee) > max(like), "罕见词应当比高频词得分高"
    assert coffee.index(max(coffee)) == 3, "应命中真正含咖啡的那条"


def test_scores_length_matches_input():
    assert len(keyword_scores_idf("x", ["a", "b", "c"])) == 3


# ── 端到端：BC-001 回归 ──

def test_natural_language_query_recalls(tmp_env):
    """BC-001 回归：自然问句必须能召回（改造前恒为 0 条）。"""
    hits = _store(tmp_env).retrieve("明翰做过什么项目？", limit=5)
    assert hits, "自然问句应能召回记忆（BC-001：改造前恒 0 条）"


def test_unanswerable_query_abstains(tmp_env):
    """不该答的问题要能空手而归——对应 Abstention 类失败模式。"""
    store = _store(tmp_env)
    # KG 里没有这些内容的记载
    for q in ("我的银行卡密码是多少", "我养了几只猫", "我上个月去了哪个国家"):
        assert store.retrieve(q, limit=5) == [], f"「{q}」应当弃权却召回了"


def test_min_score_threshold_is_configurable(tmp_env):
    """门槛可调，且调高后确实更保守——为后续标定留出接口。"""
    q = "我昨天吃了什么"
    loose = _store(tmp_env, kw_min_score=0.0).retrieve(q, limit=5)
    strict = _store(tmp_env, kw_min_score=0.9).retrieve(q, limit=5)
    assert len(strict) <= len(loose)


def test_retrieve_still_returns_uuid(tmp_env):
    """改造不能破坏返回结构——下游（引用校验、HITL）依赖 uuid。"""
    hits = _store(tmp_env).retrieve("明翰做过什么项目？", limit=3)
    assert hits and all("uuid" in h for h in hits)
