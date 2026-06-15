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


if __name__ == "__main__":
    test_default_visibility_is_private()
    test_explicit_public_visibility()
    test_visibility_persisted_to_file()
    print("\n所有测试通过 ✓")
