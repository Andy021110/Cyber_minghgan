"""
health_coach.py — 健康教练专项模式（Phase 2）

设计原则：
  · KG 只读：仅暴露 retrieve_memory 工具，无 create/update/delete
  · 协议参考：加载 protocols/bio_baseline_final.md 全文
  · 蓄水池：对话结束时 AI 自动提取 0-3 条观察写入 pending.jsonl
  · 启动检查：确认协议 life_context 是否仍然准确

用法：
    python3 health_coach.py
    python3 health_coach.py --context "切换前摘要"   （Phase 3 的 /switch 会用）
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "pipelines"))
from assistant_utils import confirm_exit, is_exit_command
from decision_log import count_pending, write_notification, write_pending

load_dotenv(Path(__file__).parent / ".env")

ROOT          = Path(__file__).parent
KG_PATH       = ROOT / "yuanbao_cyber_minghan_kg.json"
PROTOCOL_PATH = ROOT / "protocols" / "bio_baseline_final.md"
MODEL         = os.environ.get("MODEL", "deepseek-v4-pro")
MAX_TOKENS    = 2048
PENDING_THRESHOLD = 20

_GRAY  = "\033[90m"
_GREEN = "\033[92m"
_RESET = "\033[0m"
_W     = 56


# ══════════════════════════════════════════════════════════════════
#  KG 只读工具（不暴露写方法）
# ══════════════════════════════════════════════════════════════════

HEALTH_TOOLS = [
    {
        "name": "retrieve_memory",
        "description": (
            "在明翰的心智图谱（Id/Ego/Superego 三层）中检索相关记忆节点，"
            "用于了解这个人的行为模式、偏好和心理特征，以提供个性化建议。\n\n"
            "【只读权限】健康教练无权修改图谱内容。\n\n"
            "keyword: 中文关键词，如情绪词、行为动词、食物名称、压力场景等。\n"
            "limit: 返回条数上限，默认 5。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit":   {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["keyword"],
        },
    }
]


def _retrieve(keyword: str, limit: int = 5) -> list:
    """KG 字符串检索，只读，不依赖 CyberBrainStore 类。命中节点更新访问记录。"""
    kg   = json.loads(KG_PATH.read_text(encoding="utf-8"))
    node = kg["nodes"]["Cyber_Minghan"]
    kw   = keyword.lower()
    results = []
    hit_items = []
    for layer_key, layer_name in [
        ("Id_Dynamics",       "Id"),
        ("Ego_Dynamics",      "Ego"),
        ("Superego_Dynamics", "Superego"),
    ]:
        for item in node.get(layer_key, []):
            if item.get("archived"):
                continue
            haystack = " ".join([
                item.get("event_label", ""),
                item.get("description", ""),
                item.get("evidence", ""),
            ]).lower()
            if kw in haystack:
                results.append({
                    "uuid":        item.get("uuid", ""),
                    "layer":       layer_name,
                    "event_label": item.get("event_label", ""),
                    "description": item.get("description", "")[:80] + "…",
                })
                hit_items.append(item)

    results    = results[:limit]
    hit_items  = hit_items[:limit]

    if hit_items:
        now = datetime.now(timezone.utc).isoformat()
        for item in hit_items:
            item["access_count"]     = item.get("access_count", 0) + 1
            item["last_accessed_at"] = now
        tmp = KG_PATH.with_suffix(".tmp.json")
        tmp.write_text(json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(KG_PATH)

    return results


# ══════════════════════════════════════════════════════════════════
#  KG 目录摘要（事件标签拼接，约 500 token）
# ══════════════════════════════════════════════════════════════════

def build_kg_summary() -> str:
    kg   = json.loads(KG_PATH.read_text(encoding="utf-8"))
    node = kg["nodes"]["Cyber_Minghan"]
    lines = ["## 明翰心智图谱目录（只读）\n"]
    for layer_key, layer_label in [
        ("Id_Dynamics",       "Id — 本能欲望"),
        ("Ego_Dynamics",      "Ego — 现实协商"),
        ("Superego_Dynamics", "Superego — 道德规范"),
    ]:
        nodes = node.get(layer_key, [])
        lines.append(f"**{layer_label}**（{len(nodes)} 条）")
        for n in nodes:
            label = n.get("event_label", "").strip()
            if label:
                lines.append(f"  · {label}")
        lines.append("")
    lines.append("如需节点详情，请调用 retrieve_memory 工具检索。")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  协议 life_context 解析与更新
# ══════════════════════════════════════════════════════════════════

def parse_life_context(text: str) -> dict:
    """从协议 MD 文件提取 life_context 表格，返回 {字段: 值} 字典。"""
    m = re.search(
        r"\|\s*字段\s*\|\s*值\s*\|\s*\n\|[-| ]+\|\s*\n((?:\|[^|\n]+\|[^|\n]+\|\s*\n)+)",
        text,
    )
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) == 2:
            result[parts[0]] = parts[1]
    return result


def update_life_context(protocol_text: str, current_ctx: dict) -> str:
    """逐字段让用户更新 life_context，返回更新后的完整协议文本。"""
    print("\n逐字段确认（直接回车保留原值）：")
    new_ctx = {}
    for k, v in current_ctx.items():
        new_val = input(f"  {k} [{v}]: ").strip()
        new_ctx[k] = new_val if new_val else v

    new_rows = "| 字段 | 值 |\n|------|----|"
    for k, v in new_ctx.items():
        new_rows += f"\n| {k} | {v} |"

    updated = re.sub(
        r"\|\s*字段\s*\|\s*值\s*\|\s*\n\|[-| ]+\|\s*\n(?:\|[^|\n]+\|[^|\n]+\|\s*\n)+",
        new_rows + "\n",
        protocol_text,
    )
    PROTOCOL_PATH.write_text(updated, encoding="utf-8")
    write_notification(
        "protocol_updated",
        f"Health 协议 life_context 已于 {datetime.now().strftime('%Y-%m-%d')} 更新",
    )
    print(f"  {_GREEN}[OK] life_context 已更新，下次启动赛博明翰时将看到提醒{_RESET}")
    return updated


def check_protocol_freshness(protocol_text: str) -> tuple:
    """
    显示 life_context，让用户确认是否准确。
    返回 (should_continue: bool, stale: bool, updated_text: str)
    """
    ctx = parse_life_context(protocol_text)
    if not ctx:
        return True, False, protocol_text

    print(f"\n{'─'*_W}")
    print("  [协议检查] 当前协议基于以下状态制定：")
    for k, v in ctx.items():
        print(f"    {k}: {v}")
    print(f"{'─'*_W}")

    answer = input("以上信息是否仍然准确？(Y/N): ").strip().upper()
    if answer == "Y":
        return True, False, protocol_text

    print("\n协议状态可能已过期，如何处理？")
    print("  [1] 仍然进入（带「协议可能过期」警告）")
    print("  [2] 快速更新 life_context（只改背景参数，规则不动）")
    print("  [3] 退出，稍后重新蒸馏")
    while True:
        choice = input("> 你的选择: ").strip()
        if choice == "1":
            return True, True, protocol_text
        if choice == "2":
            new_text = update_life_context(protocol_text, ctx)
            return True, False, new_text
        if choice == "3":
            return False, False, protocol_text
        print("请输入 1、2 或 3")


# ══════════════════════════════════════════════════════════════════
#  System Prompt
# ══════════════════════════════════════════════════════════════════

def build_system_prompt(kg_summary: str, protocol_text: str, stale: bool) -> str:
    _WEEKDAYS = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
    now = datetime.now(timezone.utc).astimezone()
    current_time = f"{now.strftime('%Y-%m-%d %H:%M')} {_WEEKDAYS[now.weekday()]}"

    stale_note = (
        "\n⚠️ 【协议可能过期】用户确认当前生活状态可能已与协议制定时不同，"
        "建议参考时保持灵活判断。\n"
    ) if stale else ""

    return f"""[当前时间] {current_time}
{stale_note}
# 角色：明翰的专属健康教练

你是赛博明翰的健康教练，不是通用健康 AI。你了解这个人的心理模式和行为习惯，给出的建议必须结合他的真实性格，不是泛泛而谈。

## 权限
- ✓ 调用 retrieve_memory 查询明翰的心智图谱（只读）
- ✓ 参考下方协议给出具体建议
- ✗ 不能修改心智图谱（无写入权限）
- ✗ 不给执行成本极高的建议

## 说话风格
直接、有据可查、不说废话。引用协议条款时给出具体数字（如"400mg咖啡因上限"），引用图谱时说明是哪一层的哪个模式。

---

{kg_summary}

---

# Health 协议（SOP 宏观防线）

{protocol_text}
"""


# ══════════════════════════════════════════════════════════════════
#  会话结束后自动提取 pending 观察
# ══════════════════════════════════════════════════════════════════

_EXTRACT_SYSTEM = """\
你是一个行为观察员，负责从健康教练对话中提取值得记录的用户行为信息。
提取结果会进入待分类池，由下游决定写入心智图谱还是健康日志——你只负责捞出来，不负责判断路由。

【提取倾向：宁多勿少】以下任一情况均应提取：
- 用户描述了具体的饮食内容（吃了什么、量多少、感受如何）
- 用户描述了触发场景 → 行为/欲望/反应（如"卡住了就想买奶茶"）
- 用户表现出规律性偏好或补偿行为（如"每次压力大就想吃甜的"）
- 用户对健康决策的态度或倾向（如"放纵餐是合理的"）
- 用户透露的作息、运动、饮品习惯

【不提取】
- 纯粹的通用健康知识问答，对话中无用户个人信息
- 用户明确表示是虚构或假设的情景

content 格式：尽量包含场景 + 行为/选择，有触发→反应结构的优先用该格式
（例："午饭吃了草本猪软骨面，超量进食感觉很撑" 或 "工作任务重时→额外多喝两杯美式"）

输出严格 JSON 数组（禁止额外文字），最多 3 条，无内容则返回 []：
[{"content": "观察描述（60字以内）", "raw_evidence": "对话原文片段"}]"""


def extract_pending(messages: list, client: anthropic.Anthropic) -> list:
    dialogue = []
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], str):
            dialogue.append(f"用户: {m['content']}")
        elif m["role"] == "assistant" and isinstance(m["content"], list):
            text = " ".join(
                b.text for b in m["content"]
                if getattr(b, "type", "") == "text" and getattr(b, "text", "")
            ).strip()
            if text:
                dialogue.append(f"教练: {text}")

    if not dialogue:
        return []

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": "\n".join(dialogue)}],
        )
        raw = re.sub(r"^```(?:json)?\s*", "", resp.content[0].text.strip())
        raw = re.sub(r"\s*```$", "", raw).strip()
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
#  主对话循环
# ══════════════════════════════════════════════════════════════════

def run(trigger_context: str = "") -> None:
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    print("\n" + "═" * _W)
    print("  健康教练模式  （输入 exit 退出）")
    print("═" * _W)

    if not PROTOCOL_PATH.exists():
        print(f"[错误] 协议文件不存在：{PROTOCOL_PATH}")
        return

    protocol_text = PROTOCOL_PATH.read_text(encoding="utf-8")
    should_continue, stale, protocol_text = check_protocol_freshness(protocol_text)
    if not should_continue:
        print("\n[退出] 请更新协议后再进入健康教练模式。")
        return

    kg_summary    = build_kg_summary()
    system_prompt = build_system_prompt(kg_summary, protocol_text, stale)

    print(f"\n[OK] 协议已加载（{len(protocol_text)} 字）· KG 目录已注入")
    if trigger_context:
        print(f"[切换摘要] {trigger_context}")
    print("─" * _W + "\n")

    messages: list = []

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if is_exit_command(user_input):
            if confirm_exit("健康教练"):
                break
            continue

        messages.append({"role": "user", "content": user_input})
        print("\n教练: ", end="", flush=True)

        try:
            while True:
                with client.messages.stream(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=system_prompt,
                    tools=HEALTH_TOOLS,
                    messages=messages,
                ) as stream:
                    for chunk in stream.text_stream:
                        print(chunk, end="", flush=True)
                    final_msg = stream.get_final_message()

                messages.append({"role": "assistant", "content": final_msg.content})

                if final_msg.stop_reason == "end_turn":
                    print("\n")
                    break

                if final_msg.stop_reason != "tool_use":
                    print(f"\n[意外 stop_reason: {final_msg.stop_reason}]")
                    break

                tool_results = []
                for block in final_msg.content:
                    if block.type != "tool_use":
                        continue
                    kw = block.input.get("keyword", "")
                    print(f"\n{_GRAY}  [查询图谱: {kw}]{_RESET}", flush=True)
                    results = _retrieve(kw, block.input.get("limit", 5))
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(results, ensure_ascii=False),
                    })
                messages.append({"role": "user", "content": tool_results})

        except anthropic.APIError as e:
            print(f"\n[API ERROR] {e}", file=sys.stderr)
            messages.pop()

    # ── 会话结束：提取 pending 观察 ───────────────────────────────
    if messages:
        print(f"\n{_GRAY}[会话结束] 正在提取观察记录...{_RESET}", flush=True)
        observations = extract_pending(messages, client)
        if observations:
            for obs in observations:
                write_pending(
                    source_mode="health",
                    content=obs.get("content", ""),
                    raw_evidence=obs.get("raw_evidence", ""),
                    trigger_context=trigger_context,
                )
            total = count_pending("pending")
            print(f"  {_GREEN}[OK] 写入 {len(observations)} 条观察（蓄水池：{total} 条）{_RESET}")
            if total >= PENDING_THRESHOLD:
                write_notification(
                    "pending_ready",
                    f"蓄水池已达 {total} 条，下次启动赛博明翰时将自动批处理",
                )
                print("  [提示] 已达触发阈值，下次启动时自动处理")
        else:
            print(f"  {_GRAY}[OK] 本次会话无新观察{_RESET}")

    print(f"\n{'═'*_W}\n  健康教练模式已退出\n{'═'*_W}\n")


# ══════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="健康教练专项模式")
    ap.add_argument("--context", default="", help="切换前的用户意图摘要（由 /switch 传入）")
    args = ap.parse_args()
    run(trigger_context=args.context)


if __name__ == "__main__":
    main()
