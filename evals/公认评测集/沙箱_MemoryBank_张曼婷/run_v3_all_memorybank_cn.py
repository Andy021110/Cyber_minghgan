#!/usr/bin/env python3
"""
MemoryBank-CN 全量：15 用户 × ~100 探测题
协议同 V3：每用户独立 L0 episodic；L1 用空壳（全量阶段不重跑蒸馏，控成本）
隔离：不写赛博真图谱。
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
BENCH = Path(__file__).resolve().parent.parent
MB_JSON = BENCH / "MemoryBank/cn/memory_bank_cn.json"
PQ_JSONL = BENCH / "MemoryBank/cn/probing_questions_cn.jsonl"
RESULTS = SANDBOX / "results"
KG_DIR = SANDBOX / "kg" / "all_users_v3"
RESULTS.mkdir(parents=True, exist_ok=True)
KG_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CYBER_ROOT))
from dotenv import load_dotenv

load_dotenv(CYBER_ROOT / ".env", override=True)

import anthropic

import cyber_planner as cp
from memory.episodic_store import EpisodicStore


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def fingerprint(path: Path) -> dict:
    data = path.read_bytes()
    st = path.stat()
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": st.st_size}


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


def eval_system(user_name: str) -> str:
    return f"""你是长期记忆个人助理。当前用户：{user_name}。
两层记忆：
- retrieve_episode：L0 原文对话（事实题优先）
- retrieve_memory：L1 动力学图谱（可为空）

规则：事实题先 retrieve_episode；两层都无依据则说不知道；禁止编造；不是赛博明翰。
中文简洁回答。"""


TOOLS = [
    {
        "name": "retrieve_episode",
        "description": "L0 原文检索，事实题优先。",
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
        "description": "L1 图谱检索。",
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
                break
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
            epi.append(ts=day, user_text=u, assistant_text=a, source="MemoryBank")
            n += 1
    return n


def corpus_text(user: dict) -> str:
    parts = [json.dumps(user.get("meta_information") or {}, ensure_ascii=False)]
    for day, turns in (user.get("history") or {}).items():
        for t in turns or []:
            parts.append(
                f"[{day}] 用户:{(t.get('query') or '')} | 助手:{(t.get('response') or '')}"
            )
    return "\n".join(parts)


def run_probe(client, store, epi, user_name, question):
    msgs = [{"role": "user", "content": question}]
    tools = []
    answer = ""
    for _ in range(8):
        resp = client.messages.create(
            model=cp.MODEL,
            max_tokens=1024,
            system=eval_system(user_name),
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
                result = retrieve_l1_full(store, kw, limit=limit)
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


def judge(client, question, answer, corpus) -> dict:
    prompt = f"""根据【记忆语料】评判助手回答，只输出一个 JSON 对象。
【问题】{question}
【回答】{answer}
【记忆语料】
{corpus[:12000]}

{{"supported":true/false,"hallucinated":true/false,"abstained":true/false,"score":0或1,"error_code":"OK|BAD_FACT|HALLUC|MISS_DETAIL|ABSTAIN_OK|OTHER","rationale":"一句话"}}
"""
    resp = client.messages.create(
        model=cp.MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json_obj(first_text(resp.content))


def load_questions() -> dict[str, list[str]]:
    out = {}
    for line in PQ_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out.update(obj)
    return out


def main() -> None:
    started = now_iso()
    t0 = time.time()
    before = fingerprint(REAL_KG)

    users = json.loads(MB_JSON.read_text(encoding="utf-8"))
    qmap = load_questions()
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    all_rows = []
    per_user = []

    user_names = list(users.keys())
    print(f"Users={len(user_names)} questions≈{sum(len(qmap.get(u,[])) for u in user_names)}")

    for ui, name in enumerate(user_names, 1):
        user = users[name]
        questions = qmap.get(name) or []
        if not questions:
            print(f"[{ui}/{len(user_names)}] {name}: no questions, skip")
            continue

        safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", name)
        epi_path = KG_DIR / f"episodic_{safe}.jsonl"
        l1_path = KG_DIR / f"l1_{safe}.json"
        shutil.copy2(EMPTY_KG, l1_path)

        epi = EpisodicStore(epi_path)
        n0 = ingest_l0(epi, user)
        store = cp.CyberBrainStore(kg_path=l1_path)
        corpus = corpus_text(user)

        print(f"[{ui}/{len(user_names)}] {name}: L0={n0} Q={len(questions)}")
        scores = []
        for qi, q in enumerate(questions, 1):
            t1 = time.time()
            try:
                answer, tools = run_probe(client, store, epi, name, q)
                j = judge(client, q, answer, corpus)
                err = ""
            except Exception as e:
                answer, tools, j, err = "", [], {"score": 0}, str(e)
            score = int(j.get("score") or 0) if isinstance(j, dict) else 0
            scores.append(score)
            row = {
                "user": name,
                "id": f"MB-{safe}-{qi:02d}",
                "question": q,
                "answer": answer,
                "score": score,
                "n_episode": tools.count("retrieve_episode"),
                "n_memory": tools.count("retrieve_memory"),
                "judge": j,
                "answered_at": now_iso(),
                "seconds": round(time.time() - t1, 2),
                "error": err,
            }
            all_rows.append(row)
            print(f"  ({qi}/{len(questions)}) score={score} {q[:28]}")

        per_user.append(
            {
                "user": name,
                "l0_episodes": n0,
                "n_questions": len(questions),
                "correct": sum(scores),
                "accuracy": round(sum(scores) / len(scores), 4) if scores else 0,
                "display": f"{sum(scores)}/{len(questions)}",
            }
        )

        # checkpoint partial
        partial = {
            "meta": {"partial": True, "finished_users": ui, "started_at": started, "updated_at": now_iso()},
            "per_user": per_user,
            "score_so_far": {
                "correct": sum(r["score"] for r in all_rows),
                "total": len(all_rows),
            },
            "cases": all_rows,
        }
        (RESULTS / "latest_v3_all_memorybank_PARTIAL.json").write_text(
            json.dumps(partial, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    after = fingerprint(REAL_KG)
    isolation_ok = after["sha256"] == before["sha256"]
    correct = sum(r["score"] for r in all_rows)
    total = len(all_rows)
    finished = now_iso()

    fails = [r for r in all_rows if r["score"] != 1]
    out = {
        "meta": {
            "bench": "MemoryBank-CN-FULL",
            "run_name": "v3_all_users_L0_plus_empty_L1",
            "model": cp.MODEL,
            "note": "全量阶段 L1 为空壳；事实能力由 L0 episodic 承担。张曼婷单用户曾用 V2 L1+L0 打到 7/7。",
            "started_at": started,
            "finished_at": finished,
            "duration_seconds": round(time.time() - t0, 2),
            "n_users": len(per_user),
            "isolation_ok": isolation_ok,
            "real_kg_sha256": after["sha256"],
        },
        "score": {
            "correct": correct,
            "total": total,
            "accuracy": round(correct / total, 4) if total else 0,
            "display": f"{correct}/{total}",
        },
        "per_user": per_user,
        "fails": [
            {
                "id": r["id"],
                "user": r["user"],
                "question": r["question"],
                "error_code": (r.get("judge") or {}).get("error_code"),
                "answer": (r.get("answer") or "")[:200],
            }
            for r in fails
        ],
        "analysis": {
            "worth_analyzing": [
                f"总准确率 {correct}/{total}",
                f"失败 {len(fails)} 题，见 fails[]",
                "人均差异看 per_user；过低用户优先人工抽查语料/题面歧义",
                "本期 L1 未人均蒸馏；若要对齐双层满分叙事，可对失败用户补 L1",
            ]
        },
        "cases": all_rows,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS / f"v3_all_memorybank_{stamp}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "latest_v3_all_memorybank.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # remove partial pointer confusion
    partial_path = RESULTS / "latest_v3_all_memorybank_PARTIAL.json"
    if partial_path.exists():
        partial_path.unlink()

    print("\n=== DONE ===", out["score"]["display"], "isolation", isolation_ok)
    for u in per_user:
        print(f"  {u['user']}: {u['display']}")
    print("fails", len(fails))
    print("wrote", out_path)


if __name__ == "__main__":
    main()
