"""test_visibility.py — visibility 字段功能测试"""
import sys, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cyber_planner import CyberBrainStore

# ── 测试夹具 ────────────────────────────────────────────────────────

def _make_tmp_kg(tmp_dir: Path) -> Path:
    """复制生产 KG 到临时目录，返回临时路径。"""
    src = Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"
    dst = tmp_dir / "test_kg.json"
    shutil.copy(src, dst)
    return dst


# ── 场景 1：默认 visibility 为 private ────────────────────────────

def test_default_visibility_is_private():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_tmp_kg(Path(tmp))
        store = CyberBrainStore(kg_path=path)
        node = store.create(
            layer="Ego",
            event_label="测试节点",
            description="测试描述",
            evidence="测试证据",
        )
        assert node.get("visibility") == "private", \
            f"期望 'private'，得到 {node.get('visibility')!r}"
    print("✓ 场景1 通过：默认 visibility 为 private")


# ── 场景 2：显式设为 public ──────────────────────────────────────

def test_explicit_public_visibility():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_tmp_kg(Path(tmp))
        store = CyberBrainStore(kg_path=path)
        node = store.create(
            layer="Ego",
            event_label="公开节点",
            description="公开描述",
            evidence="公开证据",
            visibility="public",
        )
        assert node.get("visibility") == "public", \
            f"期望 'public'，得到 {node.get('visibility')!r}"
    print("✓ 场景2 通过：显式 public 正确写入")


# ── 场景 3：visibility 写入文件并持久化 ──────────────────────────

def test_visibility_persisted_to_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_tmp_kg(Path(tmp))
        store = CyberBrainStore(kg_path=path)
        node = store.create(
            layer="Id",
            event_label="持久化测试",
            description="描述",
            evidence="证据",
            visibility="public",
        )
        uuid = node["uuid"]
        # 重新从文件加载，确认写入磁盘
        store2 = CyberBrainStore(kg_path=path)
        lst, idx = store2._find_by_uuid(uuid)
        assert lst[idx].get("visibility") == "public", "visibility 未持久化到文件"
    print("✓ 场景3 通过：visibility 持久化到 JSON 文件")


# ── 场景 4：build_public_system_prompt 只含 public 节点 ──────────

def test_public_prompt_filters_visibility():
    import tempfile, shutil
    from pathlib import Path
    from cyber_planner import build_public_system_prompt

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        kg_path = _make_tmp_kg(tmp_path)

        # 写一个临时 persona.md
        persona_path = tmp_path / "persona.md"
        persona_path.write_text("# 测试人格\n我是测试用的人格描述。", encoding="utf-8")

        # 新建一个 public 节点和一个 private 节点
        store = CyberBrainStore(kg_path=kg_path)
        store.create(
            layer="Ego", event_label="公开行为模式",
            description="这条应该出现在公开 prompt 里",
            evidence="证据", visibility="public",
        )
        store.create(
            layer="Id", event_label="私密冲动",
            description="这条不应该出现在公开 prompt 里",
            evidence="证据", visibility="private",
        )

        prompt = build_public_system_prompt(
            persona_path=persona_path, kg_path=kg_path
        )

        assert "测试人格" in prompt, "persona.md 内容未出现在 prompt 中"
        assert "公开行为模式" in prompt, "public 节点未出现在 prompt 中"
        assert "私密冲动" not in prompt, "private 节点不应出现在 public prompt 中"

    print("✓ 场景4 通过：public prompt 正确过滤 visibility")


# ── 场景 5：process_review_decision() 透传 visibility ─────────────

def test_process_review_decision_visibility():
    """验证 process_review_decision() 的 visibility 参数透传到创建的 KG 节点。"""
    import tempfile, shutil, uuid as _uuid_mod
    from pathlib import Path
    from cyber_planner import CyberBrainStore, process_review_decision
    from decision_log import (
        write_approval_item, read_awaiting,
        _read_all, _rewrite, APPROVAL_PATH,
    )

    with tempfile.TemporaryDirectory() as tmp:
        kg_path = _make_tmp_kg(Path(tmp))

        # 直接写入一条 awaiting_approval 条目（模拟批处理已完成）
        approval_entry = write_approval_item(
            pending_id=_uuid_mod.uuid4().hex,
            source_mode="health",
            content="可见性透传测试节点",
            raw_evidence="test raw evidence for visibility",
            proposed_route="kg",
            proposed_layer="Ego",
            ai_rationale="测试用途",
        )
        item_id = approval_entry["id"]

        # 确认条目已写入待审批队列
        items = read_awaiting()
        assert any(i["id"] == item_id for i in items), "测试条目未写入待审批队列"

        store = CyberBrainStore(kg_path=kg_path)

        # 调用 process_review_decision，传入 visibility="public"
        result = process_review_decision(
            store=store,
            item_id=item_id,
            decision="approved_kg",
            visibility="public",
        )
        assert result["success"], f"process_review_decision 返回失败: {result}"

        # 重新加载 KG，确认节点的 visibility 为 "public"
        store2 = CyberBrainStore(kg_path=kg_path)
        found_node = None
        for lst in store2._node_lists():
            for node in lst:
                if node.get("event_label", "").startswith("可见性透传测试节点"):
                    found_node = node
                    break

        assert found_node is not None, "在 KG 中未找到采纳后的节点"
        assert found_node.get("visibility") == "public", \
            f"期望 visibility='public'，得到 {found_node.get('visibility')!r}"

        # 清理测试写入的 awaiting_approval 条目
        all_entries = _read_all(APPROVAL_PATH)
        cleaned = [e for e in all_entries if e.get("id") != item_id]
        _rewrite(APPROVAL_PATH, cleaned)

    print("✓ 场景5 通过：process_review_decision() 正确透传 visibility 到 KG 节点")


if __name__ == "__main__":
    test_default_visibility_is_private()
    test_explicit_public_visibility()
    test_visibility_persisted_to_file()
    test_public_prompt_filters_visibility()
    test_process_review_decision_visibility()
    print("\n所有测试通过 ✓")
