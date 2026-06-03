"""
sync_to_kg.py — 将 HITL 审查后的产物同步回 KG JSON
通用，支持任意领域。替换（不追加）对应 domain 的 sop_rules 或 kg_nodes。

用法（同步 SOP 规则）:
    python3 pipelines/sync_to_kg.py \
        --domain Health \
        --input  protocols/bio_baseline_final.md \
        --kg     yuanbao_cyber_minghan_kg.json

用法（同步 KG 节点）:
    python3 pipelines/sync_to_kg.py \
        --domain Health \
        --type   nodes \
        --input  protocols/health_nodes_reviewed.json \
        --kg     yuanbao_cyber_minghan_kg.json
"""

import json
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone

ROOT    = Path(__file__).parent.parent
KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"


def load_rules_from_md(md_path: Path) -> list:
    """从编号列表 MD 提取规则字符串。"""
    rules = re.findall(r"^\d+\.\s+(.+)", md_path.read_text(encoding="utf-8"), re.MULTILINE)
    return [r.strip() for r in rules if r.strip()]


def sync(domain: str, md_path: Path, kg_path: Path) -> None:
    rules = load_rules_from_md(md_path)
    print(f"[Sync] 读取 {len(rules)} 条规则 ← {md_path.name}")

    kg   = json.loads(kg_path.read_text(encoding="utf-8"))
    node = kg["nodes"]["Cyber_Minghan"]

    # 确保 domains 容器存在
    domains = node.setdefault("domains", {})
    bucket  = domains.setdefault(domain, {"sop_rules": [], "kg_nodes": []})

    old_count = len(bucket.get("sop_rules", []))
    bucket["sop_rules"] = rules          # 替换
    kg["updated_at"] = datetime.now(timezone.utc).isoformat()

    tmp = kg_path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(kg_path)

    print(f"[Sync] {domain}.sop_rules: {old_count} 条 → {len(rules)} 条")
    print(f"[Sync] ✓ 已写入 {kg_path.name}")


def sync_nodes(domain: str, nodes_path: Path, kg_path: Path) -> None:
    """将 HITL 审查后的 KG 节点 JSON 同步回 KG 文件（替换模式）。"""
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    if not isinstance(nodes, list):
        print(f"[Sync] 错误：节点文件应为 JSON 数组，实际类型：{type(nodes).__name__}")
        return
    print(f"[Sync] 读取 {len(nodes)} 条节点 ← {nodes_path.name}")

    kg   = json.loads(kg_path.read_text(encoding="utf-8"))
    node = kg["nodes"]["Cyber_Minghan"]

    domains = node.setdefault("domains", {})
    bucket  = domains.setdefault(domain, {"sop_rules": [], "kg_nodes": []})

    old_count = len(bucket.get("kg_nodes", []))
    bucket["kg_nodes"] = nodes          # 替换
    kg["updated_at"] = datetime.now(timezone.utc).isoformat()

    tmp = kg_path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(kg_path)

    print(f"[Sync] {domain}.kg_nodes: {old_count} 条 → {len(nodes)} 条")
    print(f"[Sync] ✓ 已写入 {kg_path.name}")


def main():
    ap = argparse.ArgumentParser(description="同步 HITL 审查结果到 KG JSON")
    ap.add_argument("--domain", required=True, help="领域名称，如 Health / Study / Work")
    ap.add_argument("--input",  required=True, type=Path, help="HITL 审查后的文件（rules→.md，nodes→.json）")
    ap.add_argument("--type",   choices=["rules", "nodes"], default="rules",
                    help="同步类型：rules=SOP规则（默认），nodes=KG因果节点")
    ap.add_argument("--kg",     type=Path, default=KG_PATH, help="KG JSON 路径（默认自动定位）")
    args = ap.parse_args()

    if not args.input.exists():
        ap.error(f"输入文件不存在：{args.input}")
    if not args.kg.exists():
        ap.error(f"KG 文件不存在：{args.kg}")

    if args.type == "nodes":
        sync_nodes(args.domain, args.input, args.kg)
    else:
        sync(args.domain, args.input, args.kg)


if __name__ == "__main__":
    main()
