"""test_alignment.py — alignment_check 功能测试"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from cyber_planner import CyberBrainStore


def _make_tmp_env(tmp_dir: Path):
    """创建临时 KG + persona.md，返回 (kg_path, persona_path)。"""
    src = Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"
    kg_path = tmp_dir / "test_kg.json"
    shutil.copy(src, kg_path)

    persona_path = tmp_dir / "persona.md"
    persona_path.write_text("# 测试人格\n深度工作偏好。", encoding="utf-8")
    return kg_path, persona_path


# ── 场景 1：无新 public 节点时返回空列表 ─────────────────────────

def test_no_new_public_nodes_returns_empty():
    from alignment_check import get_new_public_nodes_since

    with tempfile.TemporaryDirectory() as tmp:
        kg_path, _ = _make_tmp_env(Path(tmp))
        result = get_new_public_nodes_since(
            kg_path=kg_path,
            since_iso="2099-01-01T00:00:00+00:00",  # 未来时间 → 无新节点
        )
        assert result == [], f"期望空列表，得到 {result}"
    print("✓ 场景1 通过：无新节点返回空列表")


# ── 场景 2：有新 public 节点时返回正确列表 ───────────────────────

def test_new_public_nodes_returned():
    from alignment_check import get_new_public_nodes_since

    with tempfile.TemporaryDirectory() as tmp:
        kg_path, _ = _make_tmp_env(Path(tmp))
        store = CyberBrainStore(kg_path=kg_path)
        store.create(
            layer="Ego", event_label="新公开模式",
            description="描述", evidence="证据", visibility="public",
        )
        result = get_new_public_nodes_since(
            kg_path=kg_path,
            since_iso="2020-01-01T00:00:00+00:00",
        )
        labels = [n["event_label"] for n in result]
        assert "新公开模式" in labels, f"新 public 节点未返回，got {labels}"
    print("✓ 场景2 通过：新 public 节点正确返回")


# ── 场景 3：只返回 public 节点，不含 private ─────────────────────

def test_only_public_nodes_included():
    from alignment_check import get_new_public_nodes_since

    with tempfile.TemporaryDirectory() as tmp:
        kg_path, _ = _make_tmp_env(Path(tmp))
        store = CyberBrainStore(kg_path=kg_path)
        store.create(
            layer="Ego", event_label="应该出现",
            description="desc", evidence="ev", visibility="public",
        )
        store.create(
            layer="Id", event_label="不应该出现",
            description="desc", evidence="ev", visibility="private",
        )
        result = get_new_public_nodes_since(
            kg_path=kg_path,
            since_iso="2020-01-01T00:00:00+00:00",
        )
        labels = [n["event_label"] for n in result]
        assert "应该出现" in labels
        assert "不应该出现" not in labels, f"private 节点不应被返回，got {labels}"
    print("✓ 场景3 通过：private 节点被正确过滤")


if __name__ == "__main__":
    test_no_new_public_nodes_returns_empty()
    test_new_public_nodes_returned()
    test_only_public_nodes_included()
    print("\n所有测试通过 ✓")
