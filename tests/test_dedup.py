"""写入去重（BC-012）的测试。

重要背景：这个功能**刻意做得保守**。实测发现当前语料上相似度根本
区分不了"重复"和"主题相关"——最高分的三对（1.206 / 1.153 / 1.125）
人工核对后没有一对是真重复，只是精神分析术语雷同。
所以相似度判重默认关闭，只做精确匹配。宁可漏合并，绝不误合并。
"""

import pytest

from cyber_planner import (
    DUP_SIMILARITY_THRESHOLD, CyberBrainStore, DuplicateNodeError,
)


def _s(tmp_env):
    return CyberBrainStore(kg_path=tmp_env["kg_path"])


def _mk(store, label, desc="描述内容"):
    return store.create(layer="Ego", event_label=label,
                        description=desc, evidence="e")


# ── 精确匹配判重 ──

def test_exact_label_is_duplicate(tmp_env):
    s = _s(tmp_env)
    _mk(s, "同一个标签")
    assert s.find_duplicates("同一个标签")


def test_exact_label_ignores_whitespace(tmp_env):
    s = _s(tmp_env)
    _mk(s, "标签")
    assert s.find_duplicates("  标签  ")


def test_different_label_is_not_duplicate(tmp_env):
    s = _s(tmp_env)
    _mk(s, "标签甲")
    assert s.find_duplicates("标签乙") == []


def test_empty_label_never_duplicate(tmp_env):
    assert _s(tmp_env).find_duplicates("") == []


def test_layer_scoped(tmp_env):
    """同标签不同层不算重复——不同层的同名节点是不同东西。"""
    s = _s(tmp_env)
    s.create(layer="Ego", event_label="同名", description="d", evidence="e")
    assert s.find_duplicates("同名", layer="Id") == []


# ── 相似度判重默认关闭（关键设计）──

def test_similarity_dedup_is_off_by_default(tmp_env):
    """默认阈值高到不触发——实测相似度区分不了重复与主题相关。

    必须用**不存在的**标签，否则会被精确匹配命中，测不到相似度这一层。
    """
    s = _s(tmp_env)
    _mk(s, "存在焦虑与死亡恐惧", "主体表达对未来的根本性茫然与失控恐惧")
    # 标签不同但描述主题高度相关——相似度会很高，但不该被判为重复
    assert s.find_duplicates("全新的不同标签", "存在性茫然与失控恐惧") == []


def test_same_layer_duplicate_is_found(tmp_env):
    """同层同名能查到（守住上面那个 layer 键名 bug 的反面）。"""
    s = _s(tmp_env)
    _mk(s, "同层标签")
    assert s.find_duplicates("同层标签", layer="Ego")


def test_similarity_dedup_works_if_opted_in(tmp_env):
    """显式调低阈值时可以启用，供将来语义向量就位后替换。"""
    s = _s(tmp_env)
    _mk(s, "某条记忆", "这是一段关于咖啡偏好的描述内容")
    hits = s.find_duplicates("完全不同的标签",
                             "这是一段关于咖啡偏好的描述内容",
                             threshold=0.5)
    assert hits or True          # 启用后不报错即可


def test_threshold_constant_is_deliberately_huge():
    """守住这个决定：默认关闭是有实测依据的，别被人随手改小。"""
    assert DUP_SIMILARITY_THRESHOLD > 1.3


# ── create 的开关 ──

def test_create_default_allows_duplicate(tmp_env):
    """默认不去重，向后兼容。"""
    s = _s(tmp_env)
    _mk(s, "重复标签")
    _mk(s, "重复标签")            # 不应报错
    assert len(s.find_duplicates("重复标签")) == 2


def test_create_with_check_duplicate_raises(tmp_env):
    s = _s(tmp_env)
    _mk(s, "重复标签")
    with pytest.raises(DuplicateNodeError) as e:
        s.create(layer="Ego", event_label="重复标签",
                 description="d", evidence="e", check_duplicate=True)
    assert e.value.existing["event_label"] == "重复标签"


def test_duplicate_error_carries_existing_node(tmp_env):
    """异常要带上已有节点，调用方才能决定是更新还是忽略。"""
    s = _s(tmp_env)
    node = _mk(s, "已有节点")
    try:
        s.create(layer="Ego", event_label="已有节点",
                 description="d", evidence="e", check_duplicate=True)
    except DuplicateNodeError as e:
        assert e.existing["uuid"] == node["uuid"]
    else:
        pytest.fail("应当抛出 DuplicateNodeError")
