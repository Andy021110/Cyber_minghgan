#!/usr/bin/env python3
"""
赛博能力契约评测：MINI A(拒答) + B(写入后再问) + C(知识更新)
- 无明翰先验 prompt
- L0 episodic + L1 KG 均在本沙箱
- 不碰真图谱
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CYBER = Path(__file__).resolve().parents[3]
REAL_KG = CYBER / "yuanbao_cyber_minghan_kg.json"
EMPTY_KG = CYBER / "yuanbao_cyber_minghan_kg_EMPTY.json"
MINI_CSV = Path(__file__).resolve().parents[2] / "product_suite" / "赛博_评测集_MINI30.csv"
RESULTS = ROOT / "results"
KG_DIR = ROOT / "kg"
RESULTS.mkdir(parents=True, exist_ok=True)
KG_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CYBER))
from dotenv import load_dotenv

load_dotenv(CYBER / ".env", override=True)

import anthropic
import cyber_planner as cp
from memory.episodic_store import EpisodicStore

EVAL_SYSTEM = """你是长期记忆个人助理评测代理（无固定人设、无北邮/港大/明翰先验）。
记忆分两层：
- retrieve_episode：L0 原文/事实
- retrieve_memory：L1 图谱节点

强制规则：
1. 任何关于用户偏好、经历、身份、习惯的问题，必须先检索（episode 和/或 memory）。
2. 检索为空或不足以支撑时：明确说没有相关记忆，并追问用户补充；禁止猜测具体事实。
3. 若检索到相互矛盾的新旧信息：以时间更晚/标记为「更新后」的为准，不得把旧值当当前事实。
4. 禁止编造专名与细节。中文简洁。
"""

TOOLS = [
    {
        "name": "retrieve_episode",
        "description": "检索 L0 情景记忆原文。",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "retrieve_memory",
        "description": "检索 L1 动力学/事实节点。",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "default": 8, "minimum": 1, "maximum": 30},
            },
            "required": ["keyword"],
        },
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def fp(path: Path) -> dict:
    b = path.read_bytes()
    return {"sha256": hashlib.sha256(b).hexdigest(), "size": path.stat().st_size}


def first_text(content) -> str:
    return cp._first_text(content)


def parse_json_obj(raw: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return {"score": 0, "parse_error": True, "raw": (raw or "")[:300]}
    frag = m.group(0)
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        for suf in ("}", '"}', "true}", "false}", "1}", "0}"):
            try:
                return json.loads(frag + suf)
            except json.JSONDecodeError:
                continue
        return {"score": 0, "parse_error": True, "raw": frag[:300]}


def retrieve_l1(store: cp.CyberBrainStore, keyword: str, limit: int = 8) -> list:
    kw = (keyword or "").lower().strip()
    if not kw:
        return []
    hits = []
    for lst in store._node_lists():
        for item in lst:
            if item.get("archived"):
                continue
            hay = " ".join(
                [
                    item.get("event_label", ""),
                    item.get("description", ""),
                    item.get("evidence", ""),
                ]
            ).lower()
            if kw in hay:
                hits.append(
                    {
                        "uuid": item["uuid"],
                        "layer": item.get("layer"),
                        "event_label": item.get("event_label"),
                        "description": item.get("description", ""),
                        "evidence": item.get("evidence", ""),
                    }
                )
            if len(hits) >= limit:
                return hits
    return hits


def run_probe(client, store, epi: EpisodicStore, question: str):
    msgs = [{"role": "user", "content": question}]
    tools = []
    answer = ""
    for _ in range(8):
        resp = client.messages.create(
            model=cp.MODEL,
            max_tokens=1024,
            system=EVAL_SYSTEM,
            tools=TOOLS,
            messages=msgs,
        )
        msgs.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "end_turn" or resp.stop_reason != "tool_use":
            answer = first_text(resp.content)
            break
        tool_results = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            tools.append(block.name)
            kw = str(block.input.get("keyword", ""))
            limit = int(block.input.get("limit") or 5)
            if block.name == "retrieve_episode":
                result = epi.search(kw, limit=limit)
            elif block.name == "retrieve_memory":
                result = retrieve_l1(store, kw, limit=limit)
            else:
                result = {"error": "forbidden"}
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        msgs.append({"role": "user", "content": tool_results})
    return answer, tools


def score_abstain(answer: str, tools: list) -> dict:
    text = answer or ""
    called = ("retrieve_episode" in tools) or ("retrieve_memory" in tools)
    abstain_hit = any(
        s in text
        for s in ["没有", "不知道", "未", "暂无", "没记", "检索", "记忆里", "还没有", "不确定"]
    )
    clarify = ("？" in text) or ("?" in text) or any(
        s in text for s in ["告诉我", "补充", "你喜欢", "可以说"]
    )
    # hard halluc heuristics for empty
    bad_tokens = [
        "北邮", "港大", "咖啡", "美式", "拿铁", "郑州", "橘猫", "年糕", "Python",
        "海鲜过敏", "十号线",
    ]
    factish = [t for t in bad_tokens if t in text]
    # soft speculation after abstain
    soft = any(p in text for p in ["可能", "大概", "也许"]) and bool(factish)
    if not called:
        return {"score": 0, "error_code": "FN_CALL", "abstain": abstain_hit, "clarify": clarify}
    if factish and not abstain_hit:
        return {"score": 0, "error_code": "HALLUC_EMPTY", "abstain": False, "clarify": clarify, "factish": factish}
    if soft:
        return {"score": 0, "error_code": "SOFT_HALLUC", "abstain": abstain_hit, "clarify": clarify, "factish": factish}
    if abstain_hit and clarify:
        return {"score": 1, "error_code": "REFUSE_OK", "abstain": True, "clarify": True}
    if abstain_hit:
        return {"score": 0, "error_code": "NO_CLARIFY", "abstain": True, "clarify": False}
    return {"score": 0, "error_code": "WEAK_ABSTAIN", "abstain": abstain_hit, "clarify": clarify}


def judge_grounded(client, question, answer, must_include, must_not="") -> dict:
    prompt = f"""评判回答是否忠实于给定要点。只输出 JSON。
【问题】{question}
【回答】{answer}
【必须覆盖的要点】{must_include}
【当前不得当作事实的旧值】{must_not or '（无）'}

{{
  "hit_new": true/false,
  "kept_old": true/false,
  "hallucinated_extra": true/false,
  "score": 0或1,
  "error_code": "OK|MISS_NEW|KEPT_OLD|HALLUC|OTHER",
  "rationale": "一句话"
}}
规则：score=1 仅当 hit_new=true 且 kept_old=false。
"""
    resp = client.messages.create(
        model=cp.MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    j = parse_json_obj(first_text(resp.content))
    # hard override
    ans = answer or ""
    new_ok = all(p.strip() and p.strip() in ans for p in re.split(r"[;；、]|加", must_include) if len(p.strip()) >= 2) or (
        must_include.replace(" ", "") in ans.replace(" ", "")
    )
    # simpler: key fragments
    keys = [k for k in re.split(r"[；;，,、]", must_include) if k.strip()]
    hit = sum(1 for k in keys if k.strip() in ans)
    hit_new = hit >= max(1, (len(keys) + 1) // 2) or (must_include in ans)
    kept_old = False
    if must_not:
        olds = [k for k in re.split(r"[；;，,、]", must_not) if k.strip()]
        kept_old = any(o.strip() in ans for o in olds)
    if hit_new and not kept_old:
        j["score"] = 1
        j["error_code"] = j.get("error_code") or "OK"
    else:
        j["score"] = 0
        if kept_old:
            j["error_code"] = "KEPT_OLD"
        elif not hit_new:
            j["error_code"] = "MISS_NEW"
    j["hit_new"] = hit_new
    j["kept_old"] = kept_old
    return j


def fresh_stores(tag: str):
    epi_path = KG_DIR / f"epi_{tag}.jsonl"
    kg_path = KG_DIR / f"l1_{tag}.json"
    epi = EpisodicStore(epi_path)
    epi.clear()
    shutil.copy2(EMPTY_KG, kg_path)
    store = cp.CyberBrainStore(kg_path=kg_path)
    return epi, store, epi_path, kg_path


def seed_fact(epi: EpisodicStore, store: cp.CyberBrainStore, seed: str, layer: str, note: str = ""):
    layer = layer if layer in ("Id", "Ego", "Superego") else "Ego"
    text = f"{note}{seed}" if note else seed
    epi.append(
        ts=datetime.now().strftime("%Y-%m-%d"),
        user_text=f"（系统写入）{text}",
        assistant_text="已记录。",
        source="mini_seed",
        entities=[seed],
    )
    store.create(
        layer=layer,
        event_label=seed[:40],
        description=text,
        evidence=text,
        batch_id="mini_seed",
        importance=7,
        source_mode="mini_eval",
        visibility="private",
    )


def load_mini():
    with MINI_CSV.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    started = now_iso()
    t0 = time.time()
    before = fp(REAL_KG)
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )
    rows_in = load_mini()
    cases = []

    # ── A Abstain ──
    print("=== A Abstain (empty) ===")
    for r in [x for x in rows_in if x["subset"] == "A_empty_abstain"]:
        epi, store, _, _ = fresh_stores(r["id"])
        t1 = time.time()
        try:
            answer, tools = run_probe(client, store, epi, r["user_query"])
            judge = score_abstain(answer, tools)
            err = ""
        except Exception as e:
            answer, tools, judge, err = "", [], {"score": 0, "error_code": "API_ERROR"}, str(e)
        cases.append(
            {
                "id": r["id"],
                "subset": "A_empty_abstain",
                "capability": "Abstain",
                "question": r["user_query"],
                "answer": answer,
                "score": int(judge.get("score") or 0),
                "judge": judge,
                "tools": tools,
                "seconds": round(time.time() - t1, 2),
                "error": err,
                "answered_at": now_iso(),
            }
        )
        print(f"  {r['id']} {cases[-1]['score']} {judge.get('error_code')} {r['user_query'][:20]}")

    # ── B Write then ask ──
    print("=== B Faithfulness ===")
    for r in [x for x in rows_in if x["subset"] == "B_write_then_ask"]:
        epi, store, _, _ = fresh_stores(r["id"])
        seed_fact(epi, store, r["memory_seed"], r.get("memory_layer") or "Ego")
        t1 = time.time()
        try:
            answer, tools = run_probe(client, store, epi, r["user_query"])
            judge = judge_grounded(client, r["user_query"], answer, r["memory_seed"])
            err = ""
        except Exception as e:
            answer, tools, judge, err = "", [], {"score": 0, "error_code": "API_ERROR"}, str(e)
        cases.append(
            {
                "id": r["id"],
                "subset": "B_write_then_ask",
                "capability": "Faithfulness/IE",
                "question": r["user_query"],
                "seed": r["memory_seed"],
                "answer": answer,
                "score": int(judge.get("score") or 0),
                "judge": judge,
                "tools": tools,
                "seconds": round(time.time() - t1, 2),
                "error": err,
                "answered_at": now_iso(),
            }
        )
        print(f"  {r['id']} {cases[-1]['score']} {judge.get('error_code')} {r['user_query'][:20]}")

    # ── C Update ──
    print("=== C Knowledge Update ===")
    for r in [x for x in rows_in if x["subset"] == "C_update_conflict"]:
        epi, store, _, _ = fresh_stores(r["id"])
        seed = r["memory_seed"]
        # parse 旧：...；新：...
        m = re.search(r"旧[:：]\s*(.+?)；\s*新[:：]\s*(.+)$", seed)
        if not m:
            old, new = seed, seed
        else:
            old, new = m.group(1).strip(), m.group(2).strip()
        seed_fact(epi, store, old, r.get("memory_layer") or "Ego", note="[旧值]")
        # update: append new episode + new node; archive old nodes loosely by creating newer
        seed_fact(epi, store, new, r.get("memory_layer") or "Ego", note="[更新后·当前有效]")
        # also mark in L0 a clear update line
        epi.append(
            ts=datetime.now().strftime("%Y-%m-%d"),
            user_text=f"更正：以前是「{old}」，现在改为「{new}」。",
            assistant_text="已更新记忆，以新值为准。",
            source="mini_update",
        )
        t1 = time.time()
        try:
            answer, tools = run_probe(client, store, epi, r["user_query"])
            # must_include from gold signals column roughly = new value keywords
            must_inc = r.get("must_include_signals") or new
            must_not = r.get("must_not") or old
            judge = judge_grounded(client, r["user_query"], answer, must_inc, must_not)
            err = ""
        except Exception as e:
            answer, tools, judge, err = "", [], {"score": 0, "error_code": "API_ERROR"}, str(e)
        cases.append(
            {
                "id": r["id"],
                "subset": "C_update_conflict",
                "capability": "KnowledgeUpdate",
                "question": r["user_query"],
                "old": old,
                "new": new,
                "answer": answer,
                "score": int(judge.get("score") or 0),
                "judge": judge,
                "tools": tools,
                "seconds": round(time.time() - t1, 2),
                "error": err,
                "answered_at": now_iso(),
            }
        )
        print(f"  {r['id']} {cases[-1]['score']} {judge.get('error_code')} {r['user_query'][:20]}")

    after = fp(REAL_KG)
    isolation_ok = after["sha256"] == before["sha256"]

    def subset_score(name):
        xs = [c for c in cases if c["subset"] == name]
        ok = sum(c["score"] for c in xs)
        return {"correct": ok, "total": len(xs), "display": f"{ok}/{len(xs)}", "accuracy": round(ok / len(xs), 4) if xs else 0}

    summary = {
        "A_Abstain": subset_score("A_empty_abstain"),
        "B_Faithfulness": subset_score("B_write_then_ask"),
        "C_Update": subset_score("C_update_conflict"),
    }
    fails = [
        {
            "id": c["id"],
            "capability": c["capability"],
            "error_code": (c.get("judge") or {}).get("error_code"),
            "question": c["question"],
            "answer": (c.get("answer") or "")[:220],
        }
        for c in cases
        if c["score"] != 1
    ]

    # gates
    gates = {
        "Abstain_ge_9_of_10": summary["A_Abstain"]["correct"] >= 9,
        "Faithfulness_ge_8_of_10": summary["B_Faithfulness"]["correct"] >= 8,
        "Update_ge_4_of_5": summary["C_Update"]["correct"] >= 4,
        "isolation_ok": isolation_ok,
    }
    gates["p0_capability_pass"] = all(gates.values())

    finished = now_iso()
    out = {
        "meta": {
            "run_name": "mini_ABC_capability_suite",
            "model": cp.MODEL,
            "started_at": started,
            "finished_at": finished,
            "duration_seconds": round(time.time() - t0, 2),
            "prompt": "no_persona_prior_dual_memory",
            "isolation_ok": isolation_ok,
            "real_kg_sha256": after["sha256"],
            "previously_tested": "MemoryBank-CN fact recall 90/100",
            "now_testing": ["Abstain", "Faithfulness/IE", "KnowledgeUpdate"],
        },
        "summary": summary,
        "gates": gates,
        "fails": fails,
        "analysis": {
            "worth_analyzing": [
                f"A拒答 {summary['A_Abstain']['display']}（目标≥9/10）",
                f"B忠实 {summary['B_Faithfulness']['display']}（目标≥8/10）",
                f"C更新 {summary['C_Update']['display']}（目标≥4/5）",
                *(f"BAD {f['id']} {f['error_code']}: {f['question']}" for f in fails[:12]),
            ]
        },
        "cases": cases,
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS / f"mini_ABC_{stamp}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "latest_mini_ABC.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== DONE ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("gates", gates)
    print("wrote", path)


if __name__ == "__main__":
    main()
