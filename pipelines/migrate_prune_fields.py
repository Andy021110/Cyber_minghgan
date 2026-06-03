"""
migrate_prune_fields.py — KG 字段迁移（Phase 7a）

为所有现有节点追加归档/访问追踪/重要度字段，
并在 KG 根节点写入 meta.prune_config。

用法：
    python3 pipelines/migrate_prune_fields.py           # 正式迁移
    python3 pipelines/migrate_prune_fields.py --dry-run # 只打印，不写文件
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

ROOT    = Path(__file__).parent.parent
KG_PATH = ROOT / "yuanbao_cyber_minghan_kg.json"

_LAYERS = ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics")

_NODE_DEFAULTS = {
    "importance":       5,
    "access_count":     0,
    "last_accessed_at": None,
    "archived":         False,
    "archived_at":      None,
    "archive_reason":   None,
    "source_mode":      "legacy",
}

_META_DEFAULTS = {
    "prune_config": {
        "staleness_threshold":      30,
        "prune_interval_days":      90,
        "health_log_retention_days": 90,
        "max_prune_per_session":    5,
    },
    "last_prune_check": None,
}


def migrate(kg_path: Path, dry_run: bool = False) -> dict:
    kg   = json.loads(kg_path.read_text(encoding="utf-8"))
    node = kg["nodes"]["Cyber_Minghan"]

    total = 0
    for layer_key in _LAYERS:
        for item in node.get(layer_key, []):
            for field, default in _NODE_DEFAULTS.items():
                if field not in item:
                    item[field] = default
            total += 1

    # KG 根节点追加 meta
    if "meta" not in kg:
        kg["meta"] = {}
    for field, default in _META_DEFAULTS.items():
        if field not in kg["meta"]:
            kg["meta"][field] = default

    kg["updated_at"] = datetime.now(timezone.utc).isoformat()

    if dry_run:
        print(f"[DRY-RUN] 将为 {total} 个节点追加字段，不写文件")
        print(f"[DRY-RUN] meta 块：{json.dumps(kg['meta'], ensure_ascii=False, indent=2)}")
        return kg

    tmp = kg_path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(kg_path)
    print(f"[Migrate] ✓ 迁移完成：{total} 个节点，meta 已写入 {kg_path.name}")
    return kg


def main():
    ap = argparse.ArgumentParser(description="KG 字段迁移（Phase 7a）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--kg", type=Path, default=KG_PATH)
    args = ap.parse_args()
    migrate(args.kg, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
