#!/usr/bin/env python3
"""
MemoryBank「张曼婷」隔离评测。

硬约束：
- 只读写本目录 kg/ 与 results/
- 绝不写入赛博真图谱 yuanbao_cyber_minghan_kg.json
- 探测阶段仅允许 retrieve_memory（禁止 create/update/delete）
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

SANDBOX = Path(__file__).resolve().parent
CYBER_ROOT = Path(__file__).resolve().parents[3]
REAL_KG = CYBER_ROOT / "yuanbao_cyber_minghan_kg.json"
EMPTY_KG = CYBER_ROOT / "yuanbao_cyber_minghan_kg_EMPTY.json"
BENCH = Path(__file__).resolve().parent.parent
MB_JSON = BENCH / "MemoryBank/cn/memory_bank_cn.json"
PQ_JSONL = BENCH / "MemoryBank/cn/probing_questions_cn.jsonl"

USER_NAME = "张曼婷"
KG_PATH = SANDBOX / "kg" / "eval_kg_张曼婷.json"
RESULTS = SANDBOX / "results"

# 只读赛博代码与 .env；评测 store 强制指向沙箱 KG
sys.path.insert(0, str(CYBER_ROOT))
from dotenv import load_dotenv

load_dotenv(CYBER_ROOT / ".env")

import anthropic

import cyber_planner as cp

EVAL_SYSTEM_PROMPT = f"""你是一个长期记忆型个人助理评测代理。
当前服务用户：{USER_NAME}。
你的记忆全部存放在可检索的图谱中（Id/Ego/Superego 仅为存储分层，与赛博明翰人格无关）。

强制规则：
1. 回答任何关于用户偏好、经历、推荐、日期事件的问题前，必须先调用 retrieve_memory。
2. 只根据检索结果作答；检索为空或不足以支撑时，明确说不知道，并可以追问。
3. 禁止编造记忆中不存在的电影名、书名、地点、人物或细节。
4. 你不是赛博明翰，不要自称北邮/港大/明翰相关身份。
5. 回答简洁，中文。
"""

EVAL_TOOLS = [
    {
        "name": "retrieve_memory",
        "description": (
            f"检索用户「{USER_NAME}」的长期记忆节点。"
            "匹配 event_label / description / evidence。"
            "回答事实类问题前必须先检索。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "检索关键词"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["keyword"],
        },
    }
]


def fingerprint(path: Path) -> dict:
    data = path.read_bytes()
    st = path.stat()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": st.st_size,
        "mtime": st.st_mtime,
    }


def assert_real_kg_untouched(before: dict) -> dict:
    after = fingerprint(REAL_KG)
    ok = before["sha256"] == after["sha256"] and before["size"] == after["size"]
    report = {"ok": ok, "before": before, "after": after}
    (RESULTS / "REAL_KG_fingerprint_AFTER.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not ok:
        raise RuntimeError("隔离失败：赛博真图谱指纹已变化，已中止。")
    return report


def reset_sandbox_kg() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (SANDBOX / "kg").mkdir(parents=True, exist_ok=True)
    shutil.copy2(EMPTY_KG, KG_PATH)


def ingest_memorybank(store: cp.CyberBrainStore, user: dict) -> int:
    """把多日对话写入沙箱 KG（仅本文件）。"""
    n = 0
    meta = user.get("meta_information") or {}
    if meta:
        store.create(
            layer="Ego",
            event_label=f"{USER_NAME}-画像",
            description=json.dumps(meta, ensure_ascii=False),
            evidence=json.dumps(meta, ensure_ascii=False),
            batch_id="MemoryBank_ingest",
            importance=8,
            source_mode="eval_sandbox",
            visibility="private",
        )
        n += 1

    history = user.get("history") or {}
    for day, turns in history.items():
        if not isinstance(turns, list):
            continue
        for i, turn in enumerate(turns):
            q = (turn.get("query") or "").strip()
            a = (turn.get("response") or "").strip()
            if not q and not a:
                continue
            blob = f"日期:{day}\n用户:{q}\n助手:{a}"
            # 关键词检索是子串匹配：把原文完整放进三字段，便于命中
            store.create(
                layer="Ego",
                event_label=f"{day}#{i}:{q[:24]}",
                description=blob,
                evidence=blob,
                batch_id=f"MB_{day}",
                importance=5,
                source_mode="eval_sandbox",
                visibility="private",
            )
            n += 1
    return n


def history_corpus(user: dict) -> str:
    parts = [json.dumps(user.get("meta_information") or {}, ensure_ascii=False)]
    for day, turns in (user.get("history") or {}).items():
        for turn in turns or []:
            parts.append(
                f"[{day}] 用户:{(turn.get('query') or '')} | 助手:{(turn.get('response') or '')}"
            )
    return "\n".join(parts)


def run_probe(client: anthropic.Anthropic, store: cp.CyberBrainStore, question: str):
    msgs = [{"role": "user", "content": question}]
    tools_called = []
    answer = ""
    for _ in range(6):
        resp = client.messages.create(
            model=cp.MODEL,
            max_tokens=1024,
            system=EVAL_SYSTEM_PROMPT,
            tools=EVAL_TOOLS,
            messages=msgs,
        )
        msgs.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "end_turn" or resp.stop_reason != "tool_use":
            answer = cp._first_text(resp.content)
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
                        "content": "评测模式禁止该工具",
                    }
                )
                continue
            tools_called.append(block.name)
            result = store.retrieve(
                keyword=block.input.get("keyword", ""),
                limit=int(block.input.get("limit") or 10),
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
        msgs.append({"role": "user", "content": tool_results})
    return answer, tools_called


def judge(
    client: anthropic.Anthropic, question: str, answer: str, corpus: str
) -> dict:
    """用同一模型做轻量裁判：答案是否被历史支持 / 是否瞎编。"""
    prompt = f"""你是评测裁判。根据【记忆语料】判断助手回答。

【问题】
{question}

【助手回答】
{answer}

【记忆语料】（仅此为真）
{corpus[:12000]}

请只输出 JSON：
{{
  "supported": true/false,   // 答案关键事实能否被语料支持
  "hallucinated": true/false, // 是否出现语料中没有的具体事实
  "abstained": true/false,   // 是否明确表示不知道/没有记忆
  "score": 0或1,             // 1=正确或合理拒答；0=答错或瞎编
  "rationale": "一句话原因"
}}
"""
    resp = client.messages.create(
        model=cp.MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = cp._first_text(resp.content)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"score": 0, "raw": raw, "parse_error": True}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"score": 0, "raw": raw, "parse_error": True}


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    before = fingerprint(REAL_KG)
    (RESULTS / "REAL_KG_fingerprint_BEFORE.json").write_text(
        json.dumps(before, indent=2), encoding="utf-8"
    )

    reset_sandbox_kg()
    # 双重保险：store 只认沙箱路径
    assert Path(KG_PATH).resolve().parts[-3:] == (
        "沙箱_MemoryBank_张曼婷",
        "kg",
        "eval_kg_张曼婷.json",
    ) or "沙箱_MemoryBank_张曼婷" in str(KG_PATH)

    store = cp.CyberBrainStore(kg_path=KG_PATH)
    assert store._path.resolve() == KG_PATH.resolve()

    users = json.loads(MB_JSON.read_text(encoding="utf-8"))
    user = users[USER_NAME]
    n_nodes = ingest_memorybank(store, user)
    corpus = history_corpus(user)

    questions = None
    for line in PQ_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if USER_NAME in obj:
            questions = obj[USER_NAME]
            break
    if not questions:
        raise RuntimeError(f"未找到用户 {USER_NAME} 的 probing 题")

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    rows = []
    for i, q in enumerate(questions, 1):
        t0 = time.time()
        try:
            answer, tools = run_probe(client, store, q)
            j = judge(client, q, answer, corpus)
            err = ""
        except Exception as e:
            answer, tools, j, err = "", [], {"score": 0}, str(e)
        rows.append(
            {
                "id": f"MB-ZM-{i:02d}",
                "user": USER_NAME,
                "question": q,
                "answer": answer,
                "tools": "|".join(tools),
                "n_retrieve": tools.count("retrieve_memory"),
                "judge": j,
                "score": int(j.get("score") or 0) if isinstance(j, dict) else 0,
                "seconds": round(time.time() - t0, 2),
                "error": err,
            }
        )
        print(
            f"[{i}/{len(questions)}] score={rows[-1]['score']} "
            f"ret={rows[-1]['n_retrieve']} {q[:28]}"
        )
        print(" ", (answer or err).replace("\n", " ")[:160])

    # 隔离校验
    iso = assert_real_kg_untouched(before)

    total = len(rows)
    scored = sum(r["score"] for r in rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = RESULTS / f"run_{stamp}.json"
    out_md = RESULTS / f"run_{stamp}.md"
    payload = {
        "bench": "MemoryBank-CN",
        "user": USER_NAME,
        "model": cp.MODEL,
        "sandbox_kg": str(KG_PATH),
        "nodes_ingested": n_nodes,
        "score": f"{scored}/{total}",
        "accuracy": round(scored / total, 4) if total else 0,
        "isolation_ok": iso["ok"],
        "real_kg_sha256": iso["after"]["sha256"],
        "rows": rows,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# MemoryBank 张曼婷 · 隔离跑分 {stamp}",
        "",
        f"- model: `{cp.MODEL}`",
        f"- sandbox KG: `{KG_PATH.name}`（节点 {n_nodes}）",
        f"- score: **{scored}/{total}**",
        f"- 真图谱未改动: **{iso['ok']}**",
        "",
        "| id | score | retrieve | question | answer预览 |",
        "|----|------:|---------:|----------|-----------|",
    ]
    for r in rows:
        prev = (r["answer"] or r["error"]).replace("|", "\\|").replace("\n", " ")[:70]
        lines.append(
            f"| {r['id']} | {r['score']} | {r['n_retrieve']} | {r['question'][:28]} | {prev} |"
        )
    lines += [
        "",
        "## 隔离说明",
        "- 写入仅发生在本沙箱 `kg/eval_kg_张曼婷.json`",
        "- 赛博真库指纹见 `REAL_KG_fingerprint_*.json`",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n=== DONE ===", f"{scored}/{total}", "isolation", iso["ok"])
    print(out_md)


if __name__ == "__main__":
    main()
