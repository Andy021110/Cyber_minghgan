"""新旧冲突处理（BC-005 接入）的测试。

问题背景：`memory/versioning.py` 里的 supersede 逻辑早就写好了，
但**一次都没被调用过**（0/146）——模块存在不等于功能存在。

要守住的正是竞品 Mem0 栽的那个坑（issue #4956）：写入是 ADD-only，
可变属性的新旧事实并存，检索排序不含时间信号，于是问"现在在哪工作"
可能返回半年前的旧值。
"""

import pytest

from cyber_planner import CyberBrainStore


def _s(tmp_env):
    return CyberBrainStore(kg_path=tmp_env["kg_path"])


def test_supersede_marks_old_node(tmp_env):
    s = _s(tmp_env)
    old = s.create(layer="Ego", event_label="工作地点",
                   description="在 A 公司工作", evidence="e")
    new = s.supersede(old["uuid"], {"description": "在 B 公司工作"})

    lst, idx = s._find_by_uuid(old["uuid"])
    assert lst[idx].get("superseded_by") == new["uuid"], "旧节点应指向新节点"


def test_retrieve_returns_new_value_not_old(tmp_env):
    """核心用例：问"现在"应该拿到新值。"""
    s = _s(tmp_env)
    old = s.create(layer="Ego", event_label="工作地点",
                   description="在 A 公司工作", evidence="e")
    s.supersede(old["uuid"], {"description": "在 B 公司工作"})

    hits = s.retrieve("工作地点")
    descs = " ".join(h.get("description", "") for h in hits)
    assert "B 公司" in descs
    assert "A 公司" not in descs, "旧值不该出现在默认检索结果里"


def test_history_query_can_still_get_old(tmp_env):
    """历史语义查询（"我以前在哪"）需要能取到旧值。"""
    s = _s(tmp_env)
    old = s.create(layer="Ego", event_label="工作地点",
                   description="在 A 公司工作", evidence="e")
    s.supersede(old["uuid"], {"description": "在 B 公司工作"})

    hits = s.retrieve("工作地点", include_superseded=True)
    descs = " ".join(h.get("description", "") for h in hits)
    assert "A 公司" in descs


def test_new_node_records_supersedes(tmp_env):
    s = _s(tmp_env)
    old = s.create(layer="Ego", event_label="咖啡偏好",
                   description="美式不加糖", evidence="e")
    new = s.supersede(old["uuid"], {"description": "拿铁加燕麦奶"})
    assert new.get("supersedes") == old["uuid"]


def test_unsuperseded_nodes_unaffected(tmp_env):
    """没被取代的节点行为不变——不能为了新功能破坏既有检索。"""
    s = _s(tmp_env)
    s.create(layer="Ego", event_label="普通节点",
             description="一直有效的内容", evidence="e")
    assert s.retrieve("普通节点")


def test_supersede_preserves_visibility(tmp_env):
    """新节点应继承旧节点的可见性，不能因为更新就把私密内容变公开。"""
    s = _s(tmp_env)
    old = s.create(layer="Ego", event_label="敏感信息",
                   description="私密内容", evidence="e",
                   visibility="private")
    new = s.supersede(old["uuid"], {"description": "更新后的私密内容"})
    assert new.get("visibility") == "private"


def test_superseded_by_filter_itself(tmp_env):
    """不依赖归档，直接验证 superseded_by 过滤本身。

    为什么需要这一条：上面几个测试其实被"归档"掩盖了——
    supersede() 会把旧节点归档，而 _all_items() 本来就排除归档节点，
    于是过滤逻辑根本没被真正执行到。注入故障验证时发现的：
    把 `if not include_superseded` 改成 `if False`，测试照样全绿。

    这里手动只标记 superseded_by 而不归档，才能测到过滤本身。
    """
    s = _s(tmp_env)
    node = s.create(layer="Ego", event_label="标记节点",
                    description="被取代但未归档的内容", evidence="e")
    s.update(node["uuid"], superseded_by="新节点的uuid")

    # 不能断言"结果为空"——tmp_env 拷的是真实 KG（146 条），
    # 检索必然命中其他记忆。要断言的是"被标记的那条不在结果里"。
    hits = s.retrieve("标记节点")
    assert all(h["uuid"] != node["uuid"] for h in hits), "被取代的节点默认不该出现"

    back = s.retrieve("标记节点", include_superseded=True)
    assert any(h["uuid"] == node["uuid"] for h in back), "显式开启时应可取回"
