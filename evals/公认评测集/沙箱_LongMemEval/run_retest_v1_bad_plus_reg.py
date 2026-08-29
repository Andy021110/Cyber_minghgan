#!/usr/bin/env python3
"""
LongMemEval v1 复测：103 badcase + ~50 原正确回归（seed=42）
使用 question_date + retrieve_episode + list_episodes + 强化策略。
不碰赛博真图谱。
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH_ROOT = ROOT.parent
CYBER = ROOT.parents[2]
REAL_KG = CYBER / "yuanbao_cyber_minghan_kg.json"
DATA = BENCH_ROOT / "LongMemEval" / "longmemeval_oracle.json"
BASELINE = ROOT / "results" / "latest_longmemeval_oracle_full.json"
RESULTS = ROOT / "results"
KG_DIR = ROOT / "kg_retest_v1"
PARTIAL = RESULTS / "latest_retest_v1_PARTIAL.json"
REG_N = 50
SEED = 42

RESULTS.mkdir(parents=True, exist_ok=True)
KG_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CYBER))
from dotenv import load_dotenv

load_dotenv(CYBER / ".env", override=True)

import anthropic
import cyber_planner as cp
from memory.episodic_store import EpisodicStore
from memory.episodic_tools import EPISODIC_TOOLS, dispatch_episodic_tool, tool_result_content
from memory.eval_policy import eval_system_prompt


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


def is_balance_fail(row: dict) -> bool:
    err = row.get("error") or ""
    return "402" in err or "Insufficient Balance" in err


def ingest_sessions(epi: EpisodicStore, item: dict) -> int:
    epi.clear()
    n = 0
    sessions = item.get("haystack_sessions") or []
    dates = item.get("haystack_dates") or []
    for si, sess in enumerate(sessions):
        ts = dates[si] if si < len(dates) else f"session-{si}"
        buf_user, buf_asst = [], []
        for turn in sess:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role == "user":
                if buf_user and buf_asst:
                    epi.append(
                        ts=str(ts)[:48],
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
                ts=str(ts)[:48],
                user_text="\n".join(buf_user),
                assistant_text="\n".join(buf_asst),
                source="LongMemEval",
            )
            n += 1
    return n


def run_probe(client, epi: EpisodicStore, question: str, question_date: str | None):
    q = question
    if question_date:
        q = f"[Current time: {question_date}]\n{question}"
    msgs = [{"role": "user", "content": q}]
    tools_used = []
    answer = ""
    system = eval_system_prompt(question_date=question_date)
    for _ in range(12):
        resp = client.messages.create(
            model=cp.MODEL,
            max_tokens=1200,
            system=system,
            tools=EPISODIC_TOOLS,
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
            tools_used.append(block.name)
            try:
                result = dispatch_episodic_tool(epi, block.name, dict(block.input or {}))
            except Exception as e:
                result = {"error": str(e)}
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_result_content(result),
                }
            )
        msgs.append({"role": "user", "content": tool_results})
    return answer, tools_used


def normalize_score(j: dict) -> dict:
    try:
        s = float(j.get("score", 0))
    except (TypeError, ValueError):
        s = 0.0
    if s not in (0, 0.5, 1):
        s = 1.0 if s >= 0.75 else (0.5 if s >= 0.25 else 0.0)
    j["score"] = s
    return j


def judge(client, question: str, gold: str, hypothesis: str, is_abs: bool) -> dict:
    if is_abs:
        rubric = (
            "This is an abstention item. score=1 if the answer refuses/says insufficient info "
            "and does not invent the missing fact; score=0 if it asserts a specific unsupported fact."
        )
    else:
        rubric = (
            "score=1 if hypothesis matches gold key facts (paraphrase OK); "
            "0.5 partial; 0 wrong. For preference rubric answers, score=1 if response follows the preference intent. "
            "Always include a non-empty rationale."
        )
    prompt = f"""You are grading LongMemEval. Output one JSON object only.
Question: {question}
Gold: {gold}
Hypothesis: {hypothesis}
{rubric}
{{"score": 0 or 0.5 or 1, "error_code": "OK|PARTIAL|WRONG|ABS_OK|ABS_FAIL|OTHER", "rationale": "one sentence"}}
"""
    last = {"score": 0, "parse_error": True}
    for attempt in range(3):
        resp = client.messages.create(
            model=cp.MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        j = normalize_score(parse_json_obj(first_text(resp.content)))
        last = j
        if not j.get("parse_error") and (j.get("rationale") or j.get("score", 0) > 0):
            return j
        if not j.get("parse_error") and j.get("error_code"):
            return j
        time.sleep(0.4 * (attempt + 1))
    last["judge_retries"] = 3
    return last


def pick_sets(baseline: dict, data_by_id: dict) -> tuple[list[dict], list[dict]]:
    bad_ids = [c["question_id"] for c in baseline["cases"] if float(c.get("score") or 0) < 1]
    good = [c for c in baseline["cases"] if float(c.get("score") or 0) >= 1]
    by = defaultdict(list)
    for c in good:
        key = "abstention" if c.get("is_abstention") else c["question_type"]
        by[key].append(c)
    rng = random.Random(SEED)
    # stratified ~50
    quotas = {
        "temporal-reasoning": 12,
        "multi-session": 12,
        "knowledge-update": 8,
        "single-session-user": 6,
        "single-session-assistant": 5,
        "single-session-preference": 3,
        "abstention": 4,
    }
    reg = []
    for k, n in quotas.items():
        pool = list(by.get(k, []))
        rng.shuffle(pool)
        reg.extend(pool[:n])
    # pad if short
    if len(reg) < REG_N:
        leftover = [c for c in good if c["question_id"] not in {x["question_id"] for x in reg}]
        rng.shuffle(leftover)
        reg.extend(leftover[: REG_N - len(reg)])
    reg = reg[:REG_N]

    def to_items(rows, bucket: str):
        out = []
        for r in rows:
            qid = r["question_id"]
            item = data_by_id[qid]
            out.append(
                {
                    "bucket": bucket,
                    "baseline_score": float(r.get("score") or 0),
                    "item": item,
                }
            )
        return out

    bad_items = to_items([c for c in baseline["cases"] if c["question_id"] in set(bad_ids)], "bad")
    reg_items = to_items(reg, "regression")
    return bad_items, reg_items


def load_done() -> dict[str, dict]:
    if not PARTIAL.exists():
        return {}
    blob = json.loads(PARTIAL.read_text(encoding="utf-8"))
    done = {}
    for row in blob.get("cases") or []:
        if row.get("question_id") and not is_balance_fail(row):
            done[row["question_id"]] = row
    return done


def save_partial(cases, started, t0, before):
    PARTIAL.write_text(
        json.dumps(
            {
                "n": len(cases),
                "started_at": started,
                "updated_at": now_iso(),
                "elapsed_seconds": round(time.time() - t0, 2),
                "real_kg_sha256_before": before.get("sha256"),
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def agg(rows):
    if not rows:
        return {"n": 0, "avg": 0, "exact1": 0}
    s = sum(r["score"] for r in rows)
    return {
        "n": len(rows),
        "avg": round(s / len(rows), 4),
        "exact1": sum(1 for r in rows if r["score"] >= 1),
        "display": f"{s}/{len(rows)} (avg {s/len(rows):.3f})",
    }


def main():
    started = now_iso()
    t0 = time.time()
    before = fp(REAL_KG)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    data = json.loads(DATA.read_text(encoding="utf-8"))
    data_by_id = {x["question_id"]: x for x in data}
    bad_items, reg_items = pick_sets(baseline, data_by_id)
    work = bad_items + reg_items
    print(
        f"retest_v1 bad={len(bad_items)} reg={len(reg_items)} total={len(work)}",
        flush=True,
    )

    done = load_done()
    cases = list(done.values())
    done_ids = set(done)
    print(f"resume_done={len(done_ids)}", flush=True)

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    pending = [w for w in work if w["item"]["question_id"] not in done_ids]
    consecutive_402 = 0

    for i, w in enumerate(pending, 1):
        item = w["item"]
        qid = item["question_id"]
        is_abs = str(qid).endswith("_abs")
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(qid))[:80]
        epi = EpisodicStore(KG_DIR / f"epi_{safe}.jsonl")
        n_ep = ingest_sessions(epi, item)
        t1 = time.time()
        try:
            hyp, tools = run_probe(client, epi, item["question"], item.get("question_date"))
            j = judge(client, item["question"], str(item.get("answer", "")), hyp, is_abs)
            err = ""
        except Exception as e:
            hyp, tools, j, err = "", [], {"score": 0, "error_code": "API_ERROR"}, str(e)
            time.sleep(2)

        row = {
            "question_id": qid,
            "bucket": w["bucket"],
            "baseline_score": w["baseline_score"],
            "question_type": item["question_type"],
            "is_abstention": is_abs,
            "question_date": item.get("question_date"),
            "question": item["question"],
            "gold": item.get("answer"),
            "hypothesis": hyp,
            "score": float(j.get("score") or 0),
            "delta": float(j.get("score") or 0) - float(w["baseline_score"]),
            "judge": j,
            "n_episodes": n_ep,
            "n_retrieve": tools.count("retrieve_episode"),
            "n_list": tools.count("list_episodes"),
            "tools": tools,
            "seconds": round(time.time() - t1, 2),
            "answered_at": now_iso(),
            "error": err,
        }

        if is_balance_fail(row) or ("402" in err):
            consecutive_402 += 1
            print(f"[ABORT-CHECK {consecutive_402}/3] {qid} {err[:100]}", flush=True)
            if consecutive_402 >= 3:
                save_partial(cases, started, t0, before)
                print(f"Stopped on 402. kept={len(cases)}", flush=True)
                return
            continue

        consecutive_402 = 0
        cases.append(row)
        print(
            f"[{len(cases)}/{len(work)} +{i}/{len(pending)}] {w['bucket']} {qid} "
            f"base={w['baseline_score']}→{row['score']} "
            f"ret={row['n_retrieve']} list={row['n_list']} {row['seconds']}s",
            flush=True,
        )
        if len(cases) % 5 == 0 or i == len(pending):
            save_partial(cases, started, t0, before)

    after = fp(REAL_KG)
    isolation_ok = after["sha256"] == before["sha256"]

    bad_rows = [r for r in cases if r["bucket"] == "bad"]
    reg_rows = [r for r in cases if r["bucket"] == "regression"]
    fixed = sum(1 for r in bad_rows if r["score"] >= 1)
    improved = sum(1 for r in bad_rows if r["score"] > r["baseline_score"])
    regressed = [r for r in reg_rows if r["score"] < 1]

    by_type = defaultdict(list)
    for r in bad_rows:
        key = "abstention" if r["is_abstention"] else r["question_type"]
        by_type[key].append(r)

    type_fix = {}
    for k, rows in sorted(by_type.items()):
        type_fix[k] = {
            "n": len(rows),
            "fixed_ge1": sum(1 for r in rows if r["score"] >= 1),
            "fix_rate": round(sum(1 for r in rows if r["score"] >= 1) / len(rows), 3) if rows else 0,
            "avg_new": round(sum(r["score"] for r in rows) / len(rows), 3) if rows else 0,
            "avg_old": round(sum(r["baseline_score"] for r in rows) / len(rows), 3) if rows else 0,
        }

    out = {
        "meta": {
            "bench": "LongMemEval",
            "setting": "oracle_retest_v1_bad_plus_reg",
            "model": cp.MODEL,
            "memory": "L0_episodic_v1_list_plus_date",
            "seed": SEED,
            "started_at": started,
            "finished_at": now_iso(),
            "duration_seconds": round(time.time() - t0, 2),
            "isolation_ok": isolation_ok,
            "real_kg_sha256": after["sha256"],
            "note": "v1: question_date + list_episodes + policy; L1 KG untouched",
        },
        "summary": {
            "bad": {
                **agg(bad_rows),
                "fixed_ge1": fixed,
                "fix_rate": round(fixed / len(bad_rows), 4) if bad_rows else 0,
                "improved": improved,
                "improve_rate": round(improved / len(bad_rows), 4) if bad_rows else 0,
            },
            "regression": {
                **agg(reg_rows),
                "regressed_n": len(regressed),
                "regressed_ids": [r["question_id"] for r in regressed],
            },
            "bad_by_type": type_fix,
            "tool_use": {
                "mean_retrieve": round(
                    sum(r["n_retrieve"] for r in cases) / len(cases), 3
                )
                if cases
                else 0,
                "mean_list": round(sum(r["n_list"] for r in cases) / len(cases), 3)
                if cases
                else 0,
                "any_list": sum(1 for r in cases if r["n_list"] > 0),
            },
        },
        "cases": cases,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS / f"retest_v1_bad_plus_reg_{stamp}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "latest_retest_v1_bad_plus_reg.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if PARTIAL.exists():
        PARTIAL.unlink()

    print("\n=== RETEST v1 DONE ===", flush=True)
    print("bad", out["summary"]["bad"], flush=True)
    print("regression", out["summary"]["regression"], flush=True)
    print("by_type", json.dumps(type_fix, ensure_ascii=False, indent=2), flush=True)
    print("isolation", isolation_ok, "wrote", out_path, flush=True)


if __name__ == "__main__":
    main()
