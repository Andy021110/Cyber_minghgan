#!/usr/bin/env python3
"""
V2：用赛博风格「自动筛选 + 三层动力学节点」灌沙箱 KG，再测 MemoryBank 张曼婷 7 题。

隔离：只写本目录 kg/results；校验真图谱 sha256 不变。
评测模式：auto-approve（模拟 HITL 通过），不改真库。
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

USER_NAME = "张曼婷"
KG_PATH = SANDBOX / "kg" / "eval_kg_张曼婷_v2.json"
RESULTS = SANDBOX / "results"

sys.path.insert(0, str(CYBER_ROOT))
from dotenv import load_dotenv

load_dotenv(CYBER_ROOT / ".env", override=True)

import anthropic

import cyber_planner as cp

EXTRACT_SYSTEM = f"""你是「心智图谱写入筛选器」，服务于用户「{USER_NAME}」的长期记忆系统。
图谱分三层：Id / Ego / Superego（与赛博明翰同构，但主体是当前用户，不是明翰）。

任务：阅读一天的用户-助手对话，决定哪些应写入图谱（route=kg），哪些丢弃（route=skip）。

【写入 kg】
- 稳定偏好、兴趣、价值观、自我评价
- 具体经历中的可复用事实（电影/书/地点/人物/展览/麻烦事件等）——这些构成用户画像锚点
- 情绪模式、防御或自我要求（可进 Id/Superego）

【skip】
- 纯寒暄、无信息确认、助手套话
- 无法形成长期画像的一次性废话

【layer】
- Id：欲望、恐惧、紧张、亲密/逃避冲动
- Ego：现实经历、计划、兴趣实践、具体事实锚点
- Superego：自我要求、对错感、价值判断

【硬约束】
- evidence 必须保留对话原文中的关键专名（书名、电影名、画家、地名等），禁止省略
- event_label 用简洁中文；description 说明「这对理解用户意味着什么」
- 只输出 JSON 数组，不要 markdown

输出格式：
[
  {{
    "route": "kg" | "skip",
    "layer": "Id" | "Ego" | "Superego" | null,
    "event_label": "...",
    "description": "...",
    "evidence": "必须含关键专名的原文摘录",
    "importance": 1-10,
    "rationale": "不超过20字"
  }}
]
"""

EVAL_SYSTEM_PROMPT = f"""你是长期记忆个人助理评测代理。当前用户：{USER_NAME}。
记忆在 Id/Ego/Superego 图谱中；分层只表示存储结构。

规则：
1. 事实题必须先 retrieve_memory，再作答。
2. 只根据检索结果；不够就说不知道并追问。
3. 禁止编造专名与细节。
4. 不是赛博明翰，不要北邮/港大人格。
5. 中文简洁回答。
"""

EVAL_TOOLS = [
    {
        "name": "retrieve_memory",
        "description": f"检索用户「{USER_NAME}」记忆（event_label/description/evidence）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["keyword"],
        },
    }
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


def parse_json_array(raw: str) -> list:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        # 尝试截断修复：取最后一个完整 }
        frag = m.group(0)
        for i in range(len(frag), 0, -1):
            try:
                data = json.loads(frag[:i] + "]")
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue
    return []


def parse_json_obj(raw: str) -> dict:
    raw = raw.strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"score": 0, "parse_error": True, "raw": raw[:500]}
    frag = m.group(0)
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        # 补全常见截断
        for suffix in ("}", '"}', "true}", "false}", "1}", "0}"):
            try:
                return json.loads(frag + suffix)
            except json.JSONDecodeError:
                continue
        return {"score": 0, "parse_error": True, "raw": frag[:500]}


def retrieve_full(store: cp.CyberBrainStore, keyword: str, limit: int = 10) -> list:
    """评测用：在原生 retrieve 命中基础上，返回完整 description/evidence（避免 80 字截断）。"""
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
                        "importance": item.get("importance"),
                        "created_at": item.get("created_at"),
                    }
                )
            if len(hits) >= limit:
                return hits
    return hits


def day_dialogue_text(day: str, turns: list) -> str:
    lines = [f"日期: {day}"]
    for i, t in enumerate(turns or []):
        lines.append(f"[{i}] 用户: {(t.get('query') or '').strip()}")
        lines.append(f"[{i}] 助手: {(t.get('response') or '').strip()}")
    return "\n".join(lines)


def extract_day_nodes(client: anthropic.Anthropic, day: str, turns: list) -> list:
    user_msg = (
        f"请筛选并抽取应写入图谱的节点。\n\n{day_dialogue_text(day, turns)}\n\n"
        "记住：具体专名必须出现在 evidence 中。"
    )
    for attempt in range(1, 4):
        try:
            resp = client.messages.create(
                model=cp.MODEL,
                max_tokens=4096,
                system=EXTRACT_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            arr = parse_json_array(first_text(resp.content))
            if arr:
                return arr
        except Exception:
            time.sleep(attempt)
    return []


def ingest_cyber_style(client: anthropic.Anthropic, store: cp.CyberBrainStore, user: dict) -> dict:
    meta = user.get("meta_information") or {}
    stats = {
        "days": 0,
        "candidates": 0,
        "written_kg": 0,
        "skipped": 0,
        "by_layer": {"Id": 0, "Ego": 0, "Superego": 0},
        "extract_failures": 0,
    }
    if meta:
        store.create(
            layer="Ego",
            event_label=f"{USER_NAME}-基础画像",
            description="用户元信息（性格/爱好/说话语气）",
            evidence=json.dumps(meta, ensure_ascii=False),
            batch_id="MB_meta",
            importance=8,
            source_mode="eval_v2_cyber_ingest",
            visibility="private",
        )
        stats["written_kg"] += 1
        stats["by_layer"]["Ego"] += 1

    history = user.get("history") or {}
    for day, turns in history.items():
        stats["days"] += 1
        nodes = extract_day_nodes(client, day, turns)
        if not nodes:
            stats["extract_failures"] += 1
            continue
        for n in nodes:
            stats["candidates"] += 1
            route = (n.get("route") or "").lower()
            if route != "kg":
                stats["skipped"] += 1
                continue
            layer = n.get("layer") or "Ego"
            if layer not in ("Id", "Ego", "Superego"):
                layer = "Ego"
            label = (n.get("event_label") or f"{day}-记忆").strip()
            desc = (n.get("description") or "").strip() or label
            evid = (n.get("evidence") or "").strip()
            if not evid:
                stats["skipped"] += 1
                continue
            # 保险：把当天原文拼进 evidence，防专名被模型抽丢
            evid_full = f"[{day}] {evid}"
            imp = int(n.get("importance") or 5)
            store.create(
                layer=layer,
                event_label=label[:80],
                description=desc,
                evidence=evid_full,
                batch_id=f"MB_v2_{day}",
                importance=max(1, min(10, imp)),
                source_mode="eval_v2_cyber_ingest",
                visibility="private",
            )
            stats["written_kg"] += 1
            stats["by_layer"][layer] += 1
        time.sleep(0.3)
    return stats


def run_probe(client: anthropic.Anthropic, store: cp.CyberBrainStore, question: str):
    msgs = [{"role": "user", "content": question}]
    tools_called = []
    keywords = []
    answer = ""
    for _ in range(8):
        resp = client.messages.create(
            model=cp.MODEL,
            max_tokens=1024,
            system=EVAL_SYSTEM_PROMPT,
            tools=EVAL_TOOLS,
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
            if block.name != "retrieve_memory":
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "is_error": True,
                        "content": "forbidden",
                    }
                )
                continue
            tools_called.append(block.name)
            kw = str(block.input.get("keyword", ""))
            keywords.append(kw)
            result = retrieve_full(
                store, kw, limit=int(block.input.get("limit") or 10)
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        msgs.append({"role": "user", "content": tool_results})
    return answer, tools_called, keywords


def corpus_text(user: dict) -> str:
    parts = [json.dumps(user.get("meta_information") or {}, ensure_ascii=False)]
    for day, turns in (user.get("history") or {}).items():
        for t in turns or []:
            parts.append(
                f"[{day}] 用户:{(t.get('query') or '')} | 助手:{(t.get('response') or '')}"
            )
    return "\n".join(parts)


def judge(client: anthropic.Anthropic, question: str, answer: str, corpus: str) -> dict:
    prompt = f"""根据【记忆语料】评判助手回答。只输出一个 JSON 对象。

【问题】{question}
【回答】{answer}
【记忆语料】
{corpus[:14000]}

字段：
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


def analyze(rows: list, ingest_stats: dict, baseline_score: str | None) -> dict:
    fails = [r for r in rows if int(r.get("score") or 0) != 1]
    oks = [r for r in rows if int(r.get("score") or 0) == 1]
    multi_retrieve = [r for r in rows if r.get("n_retrieve", 0) >= 4]
    worth = []
    if ingest_stats.get("skipped", 0) > ingest_stats.get("written_kg", 0):
        worth.append("筛选较严：skip 多于写入，检查是否误丢事实锚点（电影/画家等）。")
    if ingest_stats.get("by_layer", {}).get("Ego", 0) == ingest_stats.get("written_kg", 0):
        worth.append("节点几乎全在 Ego：三层分化弱，动力学特色未充分体现。")
    if any("画家" in r["question"] for r in fails):
        worth.append("画家题若仍失败：对照节点 evidence 是否含达芬奇/米开朗基罗/拉斐尔。")
    if multi_retrieve:
        worth.append(
            f"{len(multi_retrieve)} 题 retrieve≥4：检索粒度/关键词策略偏抖，可看 keywords 字段。"
        )
    if baseline_score:
        worth.append(f"对比糙灌基线 {baseline_score}：看专名召回与误杀是否改善。")
    if not fails:
        worth.append("7 题全过：下一步扩用户样本，勿只报单用户。")
    for r in fails:
        worth.append(
            f"BAD {r['id']}: {r.get('judge', {}).get('error_code')} — {r['question'][:28]}"
        )
    return {
        "pass_n": len(oks),
        "fail_n": len(fails),
        "fail_ids": [r["id"] for r in fails],
        "high_retrieve_ids": [r["id"] for r in multi_retrieve],
        "worth_analyzing": worth,
    }


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = now_iso()
    t0 = time.time()
    before = fingerprint(REAL_KG)

    shutil.copy2(EMPTY_KG, KG_PATH)
    store = cp.CyberBrainStore(kg_path=KG_PATH)
    assert store._path.resolve() == KG_PATH.resolve()

    users = json.loads(MB_JSON.read_text(encoding="utf-8"))
    user = users[USER_NAME]
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    print("[1/3] cyber-style ingest …")
    ingest_stats = ingest_cyber_style(client, store, user)
    print(" ingest", ingest_stats)

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
    rows = []
    print("[2/3] probe 7 questions …")
    for i, q in enumerate(questions, 1):
        ts = now_iso()
        t1 = time.time()
        try:
            answer, tools, kws = run_probe(client, store, q)
            j = judge(client, q, answer, corpus)
            err = ""
        except Exception as e:
            answer, tools, kws, j, err = "", [], [], {"score": 0}, str(e)
        score = int(j.get("score") or 0) if isinstance(j, dict) else 0
        row = {
            "id": f"MB-ZM-{i:02d}",
            "question": q,
            "answer": answer,
            "score": score,
            "n_retrieve": tools.count("retrieve_memory"),
            "retrieve_keywords": kws,
            "judge": j,
            "answered_at": ts,
            "seconds": round(time.time() - t1, 2),
            "error": err,
        }
        rows.append(row)
        print(f"  [{i}/7] score={score} ret={row['n_retrieve']} {q[:24]}")

    iso = fingerprint(REAL_KG)
    isolation_ok = iso["sha256"] == before["sha256"]
    finished = now_iso()

    analysis = analyze(rows, ingest_stats, baseline_score="糙灌人工复核约6/7")
    layer_counts = {
        k: len(store._kg["nodes"]["Cyber_Minghan"].get(k, []))
        for k in ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics")
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {
        "meta": {
            "bench": "MemoryBank-CN",
            "user": USER_NAME,
            "run_name": "v2_cyber_ingest_auto_approve",
            "model": cp.MODEL,
            "started_at": started,
            "finished_at": finished,
            "duration_seconds": round(time.time() - t0, 2),
            "sandbox_kg": str(KG_PATH),
            "isolation_ok": isolation_ok,
            "real_kg_sha256": iso["sha256"],
            "hitl_mode": "auto_approve_for_eval",
            "retrieve_mode": "full_text_no_80char_truncation",
        },
        "ingest": {
            **ingest_stats,
            "layer_counts_in_kg": layer_counts,
        },
        "score": {
            "correct": analysis["pass_n"],
            "total": len(rows),
            "accuracy": round(analysis["pass_n"] / len(rows), 4) if rows else 0,
            "display": f"{analysis['pass_n']}/{len(rows)}",
        },
        "analysis": analysis,
        "cases": rows,
    }

    out_path = RESULTS / f"v2_cyber_ingest_{stamp}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    # 固定指针，方便你找最新
    latest = RESULTS / "latest_v2_cyber_ingest.json"
    latest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/3] done", out["score"]["display"], "isolation", isolation_ok)
    print("wrote", out_path)
    for line in analysis["worth_analyzing"]:
        print(" *", line)


if __name__ == "__main__":
    main()
