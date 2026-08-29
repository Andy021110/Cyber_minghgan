#!/usr/bin/env python3
"""
LongMemEval oracle 分层抽样（公开集）
用 L0 episodic 灌 haystack_sessions，再答题；不碰赛博真图谱。
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH_ROOT = ROOT.parent
CYBER = ROOT.parents[2]
REAL_KG = CYBER / "yuanbao_cyber_minghan_kg.json"
EMPTY_KG = CYBER / "yuanbao_cyber_minghan_kg_EMPTY.json"
DATA = BENCH_ROOT / "LongMemEval" / "longmemeval_oracle.json"
RESULTS = ROOT / "results"
KG_DIR = ROOT / "kg"
RESULTS.mkdir(parents=True, exist_ok=True)
KG_DIR.mkdir(parents=True, exist_ok=True)

# 分层样本量（合计约 52）
QUOTA = {
    "single-session-user": 8,
    "single-session-assistant": 5,
    "single-session-preference": 5,
    "knowledge-update": 10,
    "multi-session": 8,
    "temporal-reasoning": 8,
}
ABS_N = 8  # question_id 以 _abs 结尾

SEED = 42

sys.path.insert(0, str(CYBER))
from dotenv import load_dotenv

load_dotenv(CYBER / ".env", override=True)

import anthropic

import cyber_planner as cp
from memory.episodic_store import EpisodicStore

EVAL_SYSTEM = """You are a long-term memory assistant under evaluation.
You have retrieve_episode for raw dialogue memory.
Rules:
1. For personal facts, preferences, past events: call retrieve_episode before answering.
2. If evidence is insufficient, say you don't know / information is not enough; do not invent.
3. Prefer evidence from retrieved episodes; keep answers concise.
4. You are NOT Cyber Minghan; no Chinese campus persona.
"""

TOOLS = [
    {
        "name": "retrieve_episode",
        "description": "Search L0 episodic dialogue memory by keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "default": 6, "minimum": 1, "maximum": 20},
            },
            "required": ["keyword"],
        },
    }
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


def sample_items(data: list) -> list:
    rng = random.Random(SEED)
    abs_ids = {x["question_id"] for x in data if str(x["question_id"]).endswith("_abs")}
    by = defaultdict(list)
    for x in data:
        if x["question_id"] in abs_ids:
            continue
        by[x["question_type"]].append(x)
    picked = []
    for t, n in QUOTA.items():
        pool = by.get(t, [])
        rng.shuffle(pool)
        picked.extend(pool[:n])
    abs_pool = [x for x in data if x["question_id"] in abs_ids]
    rng.shuffle(abs_pool)
    picked.extend(abs_pool[:ABS_N])
    rng.shuffle(picked)
    return picked


def ingest_sessions(epi: EpisodicStore, item: dict) -> int:
    epi.clear()
    n = 0
    sessions = item.get("haystack_sessions") or []
    dates = item.get("haystack_dates") or []
    for si, sess in enumerate(sessions):
        ts = dates[si] if si < len(dates) else f"session-{si}"
        # sess is list of turns {role, content, has_answer?}
        buf_user, buf_asst = [], []
        for turn in sess:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role == "user":
                if buf_user and buf_asst:
                    epi.append(
                        ts=str(ts)[:32],
                        user_text="\n".join(buf_user),
                        assistant_text="\n".join(buf_asst),
                        source="LongMemEval",
                    )
                    n += 1
                    buf_user, buf_asst = [], []
                buf_user.append(content)
            elif role == "assistant":
                buf_asst.append(content)
        if buf_user or buf_asst:
            epi.append(
                ts=str(ts)[:32],
                user_text="\n".join(buf_user),
                assistant_text="\n".join(buf_asst),
                source="LongMemEval",
            )
            n += 1
    return n


def run_probe(client, epi: EpisodicStore, question: str):
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
            limit = int(block.input.get("limit") or 6)
            result = epi.search(kw, limit=limit) if block.name == "retrieve_episode" else []
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        msgs.append({"role": "user", "content": tool_results})
    return answer, tools


def judge(client, question: str, gold: str, hypothesis: str, is_abs: bool) -> dict:
    if is_abs:
        rubric = (
            "This is an abstention item. score=1 if the answer refuses/says insufficient info "
            "and does not invent the missing fact; score=0 if it asserts a specific unsupported fact."
        )
    else:
        rubric = (
            "score=1 if hypothesis matches gold key facts (paraphrase OK); "
            "0.5 partial; 0 wrong. For preference rubric answers, score=1 if response follows the preference intent."
        )
    prompt = f"""You are grading LongMemEval. Output one JSON object only.
Question: {question}
Gold: {gold}
Hypothesis: {hypothesis}
{rubric}
{{"score": 0 or 0.5 or 1, "error_code": "OK|PARTIAL|WRONG|ABS_OK|ABS_FAIL|OTHER", "rationale": "one sentence"}}
"""
    resp = client.messages.create(
        model=cp.MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    j = parse_json_obj(first_text(resp.content))
    try:
        s = float(j.get("score", 0))
    except (TypeError, ValueError):
        s = 0.0
    if s not in (0, 0.5, 1):
        s = 1.0 if s >= 0.75 else (0.5 if s >= 0.25 else 0.0)
    j["score"] = s
    return j


def main():
    started = now_iso()
    t0 = time.time()
    before = fp(REAL_KG)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    items = sample_items(data)
    print(f"Sampled {len(items)} items; types:", end=" ")
    from collections import Counter

    print(Counter(("ABS" if str(x["question_id"]).endswith("_abs") else x["question_type"]) for x in items))

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    cases = []
    for i, item in enumerate(items, 1):
        qid = item["question_id"]
        is_abs = str(qid).endswith("_abs")
        epi_path = KG_DIR / f"epi_{i:03d}.jsonl"
        epi = EpisodicStore(epi_path)
        n_ep = ingest_sessions(epi, item)
        t1 = time.time()
        try:
            hyp, tools = run_probe(client, epi, item["question"])
            j = judge(client, item["question"], str(item.get("answer", "")), hyp, is_abs)
            err = ""
        except Exception as e:
            hyp, tools, j, err = "", [], {"score": 0, "error_code": "API_ERROR"}, str(e)
        row = {
            "question_id": qid,
            "question_type": item["question_type"],
            "is_abstention": is_abs,
            "question": item["question"],
            "gold": item.get("answer"),
            "hypothesis": hyp,
            "score": float(j.get("score") or 0),
            "judge": j,
            "n_episodes": n_ep,
            "n_retrieve": tools.count("retrieve_episode"),
            "tools": tools,
            "seconds": round(time.time() - t1, 2),
            "answered_at": now_iso(),
            "error": err,
        }
        cases.append(row)
        print(
            f"[{i}/{len(items)}] {qid} type={item['question_type']}{'/ABS' if is_abs else ''} "
            f"score={row['score']} ret={row['n_retrieve']}"
        )
        # checkpoint
        if i % 5 == 0:
            (RESULTS / "latest_longmemeval_PARTIAL.json").write_text(
                json.dumps({"n": i, "cases": cases}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    after = fp(REAL_KG)
    isolation_ok = after["sha256"] == before["sha256"]

    def agg(rows):
        if not rows:
            return {"n": 0, "avg": 0, "exact1": 0}
        s = sum(r["score"] for r in rows)
        return {
            "n": len(rows),
            "avg": round(s / len(rows), 4),
            "exact1": sum(1 for r in rows if r["score"] >= 1),
            "display_avg": f"{s}/{len(rows)} (avg {s/len(rows):.3f})",
        }

    by_type = defaultdict(list)
    for r in cases:
        key = "abstention" if r["is_abstention"] else r["question_type"]
        by_type[key].append(r)

    summary = {k: agg(v) for k, v in sorted(by_type.items())}
    overall = agg(cases)
    fails = [
        {
            "question_id": r["question_id"],
            "question_type": r["question_type"],
            "is_abstention": r["is_abstention"],
            "score": r["score"],
            "error_code": (r.get("judge") or {}).get("error_code"),
            "question": r["question"][:120],
            "hypothesis": (r.get("hypothesis") or "")[:200],
            "gold": str(r.get("gold"))[:120],
        }
        for r in cases
        if r["score"] < 1
    ]

    finished = now_iso()
    out = {
        "meta": {
            "bench": "LongMemEval",
            "setting": "oracle_stratified_sample",
            "data_file": str(DATA),
            "model": cp.MODEL,
            "memory": "L0_episodic_only",
            "sample_seed": SEED,
            "quota": QUOTA,
            "abs_n": ABS_N,
            "started_at": started,
            "finished_at": finished,
            "duration_seconds": round(time.time() - t0, 2),
            "isolation_ok": isolation_ok,
            "real_kg_sha256": after["sha256"],
            "note": "Public LongMemEval oracle; not full 500. Compare dimensions not claim full-bench SOTA.",
        },
        "score": overall,
        "by_type": summary,
        "fails": fails,
        "cases": cases,
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS / f"longmemeval_oracle_sample_{stamp}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "latest_longmemeval_oracle_sample.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    partial = RESULTS / "latest_longmemeval_PARTIAL.json"
    if partial.exists():
        partial.unlink()

    print("\n=== DONE ===", overall)
    for k, v in summary.items():
        print(f"  {k}: n={v['n']} avg={v['avg']} exact1={v['exact1']}")
    print("fails", len(fails), "isolation", isolation_ok)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
