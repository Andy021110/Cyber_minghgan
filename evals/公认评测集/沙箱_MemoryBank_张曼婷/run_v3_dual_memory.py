#!/usr/bin/env python3
"""
V3：L0 Episodic RAG + L1 动力学 KG（复用 V2 沙箱图谱）
隔离评测 MemoryBank 张曼婷 7 题；输出带时间戳 JSON，并判定 P0 门槛。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SANDBOX = Path(__file__).resolve().parent
CYBER_ROOT = Path(__file__).resolve().parents[3]
REAL_KG = CYBER_ROOT / "yuanbao_cyber_minghan_kg.json"
EMPTY_KG = CYBER_ROOT / "yuanbao_cyber_minghan_kg_EMPTY.json"
V2_KG = SANDBOX / "kg" / "eval_kg_张曼婷_v2.json"
L1_KG = SANDBOX / "kg" / "eval_kg_张曼婷_v3_l1.json"
L0_PATH = SANDBOX / "kg" / "episodic_张曼婷_v3.jsonl"
BENCH = Path(__file__).resolve().parent.parent
MB_JSON = BENCH / "MemoryBank/cn/memory_bank_cn.json"
PQ_JSONL = BENCH / "MemoryBank/cn/probing_questions_cn.jsonl"
RESULTS = SANDBOX / "results"
USER_NAME = "张曼婷"

sys.path.insert(0, str(CYBER_ROOT))
from dotenv import load_dotenv

load_dotenv(CYBER_ROOT / ".env", override=True)

import anthropic

import cyber_planner as cp
from memory.episodic_store import EpisodicStore

EVAL_SYSTEM = f"""你是长期记忆个人助理。当前用户：{USER_NAME}。
你有两层记忆：
- retrieve_episode：L0 情景层，对话原文，适合事实/专名/某日事件
- retrieve_memory：L1 心智层，提炼后的 Id/Ego/Superego 节点

规则：
1. 事实题（电影、书、画家、公园景色、博物馆、某日麻烦）必须先 retrieve_episode。
2. 可再 retrieve_memory 作补充，但不得与 L0 原文冲突；冲突以 L0 为准。
3. 两层都无依据时，明确说不知道并追问。
4. 禁止编造专名与剧情。
5. 不是赛博明翰，不要北邮/港大人设。
6. 中文简洁回答。
"""

TOOLS = [
    {
        "name": "retrieve_episode",
        "description": "从 L0 原文对话记忆检索。事实题优先调用。",
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
        "description": "从 L1 三层动力学图谱检索提炼节点。",
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


def fingerprint(path: Path) -> dict:
    data = path.read_bytes()
    st = path.stat()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": st.st_size,
        "mtime": st.st_mtime,
    }


def first_text(content) -> str:
    return cp._first_text(content)


def parse_json_obj(raw: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return {"score": 0, "parse_error": True, "raw": (raw or "")[:400]}
    frag = m.group(0)
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        for suf in ("}", '"}', "true}", "false}", "1}", "0}"):
            try:
                return json.loads(frag + suf)
            except json.JSONDecodeError:
                continue
        return {"score": 0, "parse_error": True, "raw": frag[:400]}


def retrieve_l1_full(store: cp.CyberBrainStore, keyword: str, limit: int = 8) -> list:
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


def ingest_l0(epi: EpisodicStore, user: dict) -> int:
    epi.clear()
    n = 0
    for day, turns in (user.get("history") or {}).items():
        for turn in turns or []:
            u = (turn.get("query") or "").strip()
            a = (turn.get("response") or "").strip()
            if not u and not a:
                continue
            epi.append(
                ts=day,
                user_text=u,
                assistant_text=a,
                source="MemoryBank",
            )
            n += 1
    return n


def prepare_l1() -> Path:
    """优先复用 V2 蒸馏图谱；若无则用空壳。"""
    if V2_KG.exists():
        shutil.copy2(V2_KG, L1_KG)
    else:
        shutil.copy2(EMPTY_KG, L1_KG)
    return L1_KG


def run_probe(client, store_l1, epi: EpisodicStore, question: str):
    msgs = [{"role": "user", "content": question}]
    tools_called = []
    tool_trace = []
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
            tools_called.append(block.name)
            kw = str(block.input.get("keyword", ""))
            limit = int(block.input.get("limit") or (5 if block.name == "retrieve_episode" else 8))
            if block.name == "retrieve_episode":
                result = epi.search(kw, limit=limit)
            elif block.name == "retrieve_memory":
                result = retrieve_l1_full(store_l1, kw, limit=limit)
            else:
                result = {"error": "forbidden"}
            tool_trace.append({"tool": block.name, "keyword": kw, "n": len(result) if isinstance(result, list) else 0})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        msgs.append({"role": "user", "content": tool_results})
    return answer, tools_called, tool_trace


def corpus_text(user: dict) -> str:
    parts = [json.dumps(user.get("meta_information") or {}, ensure_ascii=False)]
    for day, turns in (user.get("history") or {}).items():
        for t in turns or []:
            parts.append(
                f"[{day}] 用户:{(t.get('query') or '')} | 助手:{(t.get('response') or '')}"
            )
    return "\n".join(parts)


def judge(client, question, answer, corpus) -> dict:
    prompt = f"""根据【记忆语料】评判助手回答，只输出一个 JSON 对象。
【问题】{question}
【回答】{answer}
【记忆语料】
{corpus[:14000]}

{{
  "supported": true/false,
  "hallucinated": true/false,
  "abstained": true/false,
  "score": 0或1,
  "error_code": "OK|BAD_FACT|HALLUC|MISS_DETAIL|ABSTAIN_OK|OTHER",
  "rationale": "一句话"
}}
"""
    resp = client.messages.create(
        model=cp.MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json_obj(first_text(resp.content))


def evaluate_gates(rows: list, isolation_ok: bool) -> dict:
    hard_ids = {"MB-ZM-03", "MB-ZM-05", "MB-ZM-07"}
    by_id = {r["id"]: r for r in rows}
    correct = sum(1 for r in rows if int(r.get("score") or 0) == 1)
    total = len(rows)
    g1 = correct >= 6
    g2 = correct >= 6  # vs V2=4；用 ≥6 表达「明显更好且达线」
    g3 = all(int(by_id[i].get("score") or 0) == 1 for i in hard_ids if i in by_id)
    g4 = isolation_ok
    return {
        "G1_zhangmanting_ge_6_of_7": {"pass": g1, "value": f"{correct}/{total}"},
        "G2_better_than_v2_4of7": {"pass": g2, "value": f"{correct}/{total}", "baseline_v2": "4/7"},
        "G3_hard_three_all_pass": {
            "pass": g3,
            "value": {i: int(by_id[i].get("score") or 0) for i in hard_ids},
        },
        "G4_real_kg_untouched": {"pass": g4, "value": g4},
        "p0_all_pass": g1 and g2 and g3 and g4,
    }


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = now_iso()
    t0 = time.time()
    before = fingerprint(REAL_KG)

    users = json.loads(MB_JSON.read_text(encoding="utf-8"))
    user = users[USER_NAME]
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    print("[1/4] ingest L0 episodic …")
    epi = EpisodicStore(L0_PATH)
    n0 = ingest_l0(epi, user)
    print(" L0 episodes", n0)

    print("[2/4] prepare L1 kg …")
    prepare_l1()
    store = cp.CyberBrainStore(kg_path=L1_KG)
    l1_counts = {
        k: len(store._kg["nodes"]["Cyber_Minghan"].get(k, []))
        for k in ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics")
    }
    print(" L1", l1_counts)

    questions = None
    for line in PQ_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if USER_NAME in obj:
            questions = obj[USER_NAME]
            break
    assert questions
    corpus = corpus_text(user)

    print("[3/4] probe …")
    rows = []
    for i, q in enumerate(questions, 1):
        ts = now_iso()
        t1 = time.time()
        try:
            answer, tools, trace = run_probe(client, store, epi, q)
            j = judge(client, q, answer, corpus)
            err = ""
        except Exception as e:
            answer, tools, trace, j, err = "", [], [], {"score": 0}, str(e)
        score = int(j.get("score") or 0) if isinstance(j, dict) else 0
        rows.append(
            {
                "id": f"MB-ZM-{i:02d}",
                "question": q,
                "answer": answer,
                "score": score,
                "tools": tools,
                "n_episode": tools.count("retrieve_episode"),
                "n_memory": tools.count("retrieve_memory"),
                "tool_trace": trace,
                "judge": j,
                "answered_at": ts,
                "seconds": round(time.time() - t1, 2),
                "error": err,
            }
        )
        print(
            f"  [{i}/7] score={score} ep={rows[-1]['n_episode']} "
            f"mem={rows[-1]['n_memory']} {q[:22]}"
        )

    after = fingerprint(REAL_KG)
    isolation_ok = after["sha256"] == before["sha256"]
    gates = evaluate_gates(rows, isolation_ok)
    finished = now_iso()
    correct = sum(r["score"] for r in rows)

    out = {
        "meta": {
            "bench": "MemoryBank-CN",
            "user": USER_NAME,
            "run_name": "v3_dual_memory_L0_L1",
            "model": cp.MODEL,
            "started_at": started,
            "finished_at": finished,
            "duration_seconds": round(time.time() - t0, 2),
            "l0_path": str(L0_PATH),
            "l1_path": str(L1_KG),
            "l0_episodes": n0,
            "l1_layer_counts": l1_counts,
            "isolation_ok": isolation_ok,
            "real_kg_sha256": after["sha256"],
        },
        "score": {
            "correct": correct,
            "total": len(rows),
            "accuracy": round(correct / len(rows), 4),
            "display": f"{correct}/{len(rows)}",
        },
        "gates": gates,
        "comparisons": {
            "v1_rough_l1_human": "~6/7",
            "v2_distill_l1_only": "4/7",
            "v3_dual": f"{correct}/{len(rows)}",
        },
        "analysis": {
            "worth_analyzing": [
                *(
                    [f"FAIL {r['id']} {r.get('judge', {}).get('error_code')}: {r['question']}"]
                    for r in rows
                    if r["score"] != 1
                ),
                f"P0 all pass = {gates['p0_all_pass']}",
                "若 G3 仍挂：查 tool_trace 是否调用了 retrieve_episode 以及 L0 是否含原文。",
            ]
        },
        "cases": rows,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS / f"v3_dual_memory_{stamp}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "latest_v3_dual_memory.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("[4/4] done", out["score"]["display"], "P0", gates["p0_all_pass"])
    for k, v in gates.items():
        if k == "p0_all_pass":
            continue
        print(f"  {k}: {'PASS' if v['pass'] else 'FAIL'} ({v['value']})")
    print("wrote", out_path)


if __name__ == "__main__":
    main()
