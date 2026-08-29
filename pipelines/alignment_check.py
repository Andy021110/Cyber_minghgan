"""
alignment_check.py — MD vs KG 对齐检查

用法：
    python3 pipelines/alignment_check.py

功能：
    收集自 KG meta.last_alignment_at 以来新增的 visibility=public 节点，
    若数量 ≤ INLINE_THRESHOLD 则直接打印供人工比对；
    若超过阈值则调用 Claude 归纳出关键漂移点，再交用户裁决。
    用户确认后更新 meta.last_alignment_at。
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from cyber_planner import KG_PATH, CyberBrainStore

PERSONA_PATH     = _ROOT / "persona.md"
INLINE_THRESHOLD = 10  # 节点数 ≤ 此值时直接展示，不调用 AI


# ══════════════════════════════════════════════════════════════════
#  核心查询函数（可被测试 import）
# ══════════════════════════════════════════════════════════════════

def get_new_public_nodes_since(
    since_iso: str,
    kg_path: Path = KG_PATH,
) -> list:
    """返回 created_at > since_iso 且 visibility=public 的活跃节点列表。"""
    store = CyberBrainStore(kg_path=kg_path)
    result = []
    for lst in store._node_lists():
        for node in lst:
            if node.get("archived"):
                continue
            if node.get("visibility") != "public":
                continue
            created = node.get("created_at", "")
            if created > since_iso:
                result.append(node)
    return result


def _get_last_alignment_at(kg_path: Path = KG_PATH) -> str:
    """从 KG meta 读取上次对齐时间，不存在则返回 Unix 起点。"""
    data = json.loads(kg_path.read_text(encoding="utf-8"))
    return data.get("meta", {}).get("last_alignment_at", "1970-01-01T00:00:00+00:00")


def _set_last_alignment_at(kg_path: Path = KG_PATH) -> None:
    """将 meta.last_alignment_at 更新为当前 UTC 时间。"""
    data = json.loads(kg_path.read_text(encoding="utf-8"))
    data.setdefault("meta", {})["last_alignment_at"] = datetime.now(timezone.utc).isoformat()
    kg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════
#  展示与 AI 辅助
# ══════════════════════════════════════════════════════════════════

def _print_nodes(nodes: list) -> None:
    print("\n── 新增 public 节点 ─────────────────────────────────────\n")
    for i, n in enumerate(nodes, 1):
        print(f"  [{i}] [{n['layer']}] {n['event_label']}")
        print(f"      {n.get('description', '')}\n")


def _ai_summarize_drift(persona_text: str, nodes: list) -> str:
    """调用 Claude 归纳 persona.md 与新节点的漂移点，返回摘要文本。"""
    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )
    nodes_text = "\n".join(
        f"- [{n['layer']}] {n['event_label']}: {n.get('description', '')}"
        for n in nodes
    )
    prompt = f"""以下是当前的 persona.md 内容：

{persona_text}

---

以下是自上次对齐以来新增的公开 KG 节点：

{nodes_text}

---

请对比 persona.md 和新增节点，找出 3-5 个关键的漂移点或矛盾处。
漂移点是指：persona.md 的描述已经不能反映 KG 的新数据，需要更新 persona.md 的地方。
每条漂移点简短描述（一句话），并说明建议如何修改 persona.md。
只列出真正有意义的漂移，无漂移时直接输出"无明显漂移"。"""

    response = client.messages.create(
        model=os.environ.get("MODEL", "deepseek-v4-pro"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ══════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════

def run(kg_path: Path = KG_PATH, persona_path: Path = PERSONA_PATH) -> None:
    since = _get_last_alignment_at(kg_path)
    nodes = get_new_public_nodes_since(since_iso=since, kg_path=kg_path)

    print(f"\n[对齐检查] 上次对齐：{since[:10]}")
    print(f"[对齐检查] 发现 {len(nodes)} 条新 public 节点\n")

    if len(nodes) == 0:
        print("✓ 无需更新，persona.md 与 KG 已同步。")
        return

    persona_text = persona_path.read_text(encoding="utf-8") if persona_path.exists() else ""

    if len(nodes) <= INLINE_THRESHOLD:
        print("节点数量较少，直接展示供人工对比：")
        print("\n── 当前 persona.md ───────────────────────────────────────\n")
        print(persona_text)
        _print_nodes(nodes)
    else:
        print(f"节点数量 {len(nodes)} 超过阈值 {INLINE_THRESHOLD}，调用 AI 初步归纳漂移点…\n")
        summary = _ai_summarize_drift(persona_text, nodes)
        print("── AI 归纳的漂移点 ────────────────────────────────────────\n")
        print(summary)
        print()

    answer = input("确认已查看并处理完成？记录本次对齐时间？(Y/N): ").strip().upper()
    if answer == "Y":
        _set_last_alignment_at(kg_path)
        print(f"✓ 对齐时间已更新至 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    else:
        print("已取消，下次运行时仍会包含本次节点。")


if __name__ == "__main__":
    run()
