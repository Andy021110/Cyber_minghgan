"""
migrate_uuid.py
为 yuanbao_cyber_minghan_kg.json 中的所有节点注入 UUID 主键。
"""

import json
import uuid
from pathlib import Path

KG_PATH = Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"

kg = json.loads(KG_PATH.read_text(encoding="utf-8"))

counts = {}

# 三层动力学节点
node = kg["nodes"]["Cyber_Minghan"]
for layer_key in ("Id_Dynamics", "Superego_Dynamics", "Ego_Dynamics"):
    injected = 0
    for item in node.get(layer_key, []):
        if "uuid" not in item:
            item["uuid"] = uuid.uuid4().hex
            injected += 1
    counts[layer_key] = injected

# 顶层 interactions
injected = 0
for item in kg.get("interactions", []):
    if "uuid" not in item:
        item["uuid"] = uuid.uuid4().hex
        injected += 1
counts["interactions"] = injected

KG_PATH.write_text(json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8")

total = sum(counts.values())
print(f"UUID 注入完成：{counts}，合计 {total} 条")
