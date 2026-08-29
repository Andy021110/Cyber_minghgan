#!/usr/bin/env python3
"""Translate LongMemEval badcases into a full Chinese report."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CYBER = Path(__file__).resolve().parents[3]  # 元宝-明翰
SRC = ROOT / "results" / "badcases_longmemeval_oracle_full.json"
OUT_JSON = ROOT / "results" / "badcases_longmemeval_oracle_full_zh.json"
OUT_MD = ROOT / "results" / "badcases_longmemeval_oracle_full_zh.md"
PARTIAL = ROOT / "results" / "badcases_zh_PARTIAL.json"

TYPE_ZH = {
    "abstention": "拒答（Abstention）",
    "knowledge-update": "知识更新（Knowledge Update）",
    "multi-session": "多会话推理（Multi-session）",
    "single-session-assistant": "单会话-助手信息（IE-Assistant）",
    "single-session-preference": "单会话-个性化偏好（Preference）",
    "single-session-user": "单会话-用户事实（IE-User）",
    "temporal-reasoning": "时间推理（Temporal）",
}

sys.path.insert(0, str(CYBER))
from dotenv import load_dotenv

load_dotenv(CYBER / ".env", override=True)

import anthropic
import cyber_planner as cp


def first_text(content) -> str:
    return cp._first_text(content)


def parse_json_obj(raw: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return {}
    frag = m.group(0)
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        for suf in ("}", '"}'):
            try:
                return json.loads(frag + suf)
            except json.JSONDecodeError:
                continue
        return {}


def translate_one(client, b: dict) -> dict:
    prompt = f"""把下面 LongMemEval badcase 译成中文。只输出一个 JSON 对象，不要 markdown。
字段：
- question_zh: 题目中文
- gold_zh: 金标中文（完整翻译）
- hypothesis_zh: 模型回答中文（完整翻译，保留原有列举结构）
- rationale_zh: 裁判理由中文；若原文为空则写「（裁判无理由/解析失败）」
- fail_note_zh: 一句话中文归因（例如：跨会话漏计；偏好未贴合；新旧值冲突未取最终态；疑似拒答却被误杀）

原文：
question_id: {b.get('question_id')}
type: {b.get('question_type')} abstention={b.get('is_abstention')}
score: {b.get('score')}
error_code: {b.get('error_code')}
question: {b.get('question')}
gold: {b.get('gold')}
hypothesis: {b.get('hypothesis')}
rationale: {b.get('rationale')}
"""
    for attempt in range(3):
        resp = client.messages.create(
            model=cp.MODEL,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        j = parse_json_obj(first_text(resp.content))
        if j.get("question_zh") and ("hypothesis_zh" in j or "gold_zh" in j):
            return j
        time.sleep(0.6 * (attempt + 1))
    return {
        "question_zh": str(b.get("question") or ""),
        "gold_zh": str(b.get("gold") or ""),
        "hypothesis_zh": str(b.get("hypothesis") or "") or "（空回答）",
        "rationale_zh": "（翻译失败，保留原文） " + str(b.get("rationale") or ""),
        "fail_note_zh": "翻译失败",
        "translate_error": True,
    }


def render_md(blob: dict) -> str:
    s = blob["summary"]
    lines = []
    lines.append("# LongMemEval Oracle 全量 500｜Badcase 完整中文版")
    lines.append("")
    lines.append("- 来源：`latest_longmemeval_oracle_full.json` / `badcases_longmemeval_oracle_full.json`")
    lines.append("- 准则：score < 1（含 0 分与 0.5 分）")
    lines.append(
        f"- 数量：**{s['n_bad']}** / {s['n_total_cases']}（0分 {s['n_zero']} · 半分 {s['n_partial_0.5']}）"
    )
    lines.append(f"- 总分对照：{blob['meta'].get('overall_score', {}).get('display_avg')}")
    lines.append("- 说明：题目 / 金标 / 模型回答 / 裁判理由均为中文翻译，便于通读；专有名词尽量保留原文。")
    lines.append("")
    lines.append("## 分型统计")
    lines.append("")
    lines.append("| 题型 | bad数 | bad内均分 | 未检索 | 空回答 |")
    lines.append("|------|------:|----------:|-------:|-------:|")
    for k, v in s["by_type"].items():
        lines.append(
            f"| {TYPE_ZH.get(k, k)} | {v['n']} | {v['avg_score']} | {v['ret0']} | {v['empty_hyp']} |"
        )
    lines.append("")
    lines.append("## 失败模式速览")
    lines.append("")
    lines.append("1. **时间/多会话计数漏项**：召回到部分证据，枚举不全导致 2≠4、2≠3。")
    lines.append("2. **知识更新未取最终态**：新旧值并列「无法确认」，题面要的是当前/最终事实。")
    lines.append("3. **个性化偏好未硬约束**：给出通用建议，未贴合历史里的软件/酒店偏好。")
    lines.append("4. **裁判噪声**：拒答其实合格但 rationale 为空被打 0；preference 亦有无理由 0 分。")
    lines.append("")

    # group by type
    by = {}
    for b in blob["all_bads_zh"]:
        key = "abstention" if b.get("is_abstention") else b["question_type"]
        by.setdefault(key, []).append(b)

    order = [
        "temporal-reasoning",
        "multi-session",
        "single-session-preference",
        "knowledge-update",
        "abstention",
        "single-session-user",
        "single-session-assistant",
    ]
    idx = 0
    for k in order:
        rows = by.get(k) or []
        if not rows:
            continue
        lines.append(f"## {TYPE_ZH.get(k, k)}（{len(rows)}）")
        lines.append("")
        for b in rows:
            idx += 1
            lines.append(
                f"### {idx}. `{b['question_id']}`｜score={b['score']}｜检索次数={b.get('n_retrieve')}｜{b.get('error_code')}"
            )
            lines.append(f"- **归因**：{b.get('fail_note_zh') or '（无）'}")
            lines.append(f"- **题**：{b.get('question_zh')}")
            lines.append(f"- **金标**：{b.get('gold_zh')}")
            hyp = b.get("hypothesis_zh") or "（空回答）"
            lines.append(f"- **模型回答**：\n\n{hyp}\n")
            lines.append(f"- **裁判**：{b.get('rationale_zh')}")
            lines.append("")
    return "\n".join(lines)


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    bads = src["all_bads"]
    done = {}
    if PARTIAL.exists():
        try:
            done = {
                x["question_id"]: x
                for x in json.loads(PARTIAL.read_text(encoding="utf-8")).get("all_bads_zh", [])
                if x.get("question_id") and not x.get("translate_error")
            }
        except Exception:
            done = {}

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    out_rows = []
    for i, b in enumerate(bads, 1):
        qid = b["question_id"]
        if qid in done:
            out_rows.append(done[qid])
            print(f"[{i}/{len(bads)}] skip {qid}", flush=True)
            continue
        zh = translate_one(client, b)
        row = {
            **{k: b.get(k) for k in (
                "question_id", "question_type", "is_abstention", "score",
                "error_code", "n_retrieve", "n_episodes", "fail_tags",
            )},
            **zh,
            "question_en": b.get("question"),
            "gold_en": b.get("gold"),
            "hypothesis_en": b.get("hypothesis"),
            "rationale_en": b.get("rationale"),
        }
        out_rows.append(row)
        done[qid] = row
        print(
            f"[{i}/{len(bads)}] {qid} type={b['question_type']} note={row.get('fail_note_zh','')[:40]}",
            flush=True,
        )
        if i % 5 == 0 or i == len(bads):
            PARTIAL.write_text(
                json.dumps({"n": len(out_rows), "all_bads_zh": out_rows}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    blob = {
        "meta": {
            **src.get("meta", {}),
            "language": "zh",
            "translated_with": cp.MODEL,
        },
        "summary": src["summary"],
        "all_bads_zh": out_rows,
    }
    OUT_JSON.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(render_md(blob), encoding="utf-8")
    if PARTIAL.exists():
        PARTIAL.unlink()
    print("wrote", OUT_MD, flush=True)
    print("wrote", OUT_JSON, flush=True)


if __name__ == "__main__":
    main()
