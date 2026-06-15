"""
cyber_planner.py
赛博明翰 · 交互式认知对话终端（Interactive CLI）

用法：
    python3 cyber_planner.py
    输入 exit / quit 退出

内置指令：
    /switch health   切换至健康教练模式（单向，需确认）
    /review          逐条审批待处理分类结果（写入 KG 或 health_log）
    /<其他指令>      路由至 KG 管理员 Tool Use Agent
"""

import json
import os
import sys
import uuid as _uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent / "pipelines"))
from decision_log import (
    read_unconsumed_notifications,
    consume_notification,
    read_awaiting,
    count_pending,
    resolve_approval,
    update_pending_status,
    write_notification,
)

# ── 配置 ──────────────────────────────────────────────────────────
KG_PATH       = Path(__file__).parent / "yuanbao_cyber_minghan_kg.json"
MODEL         = "claude-sonnet-4-6"
MAX_TOKENS    = 2048
REFLECT_EVERY = 5   # 每隔多少轮触发一次反刍

# 专项模式路由表：新增领域只需在这里加一行
_MODE_MAP = {
    "health": "health_coach",
}

HEALTH_LOG_PATH = Path(__file__).parent / "decision_logs" / "health_log.jsonl"
BATCH_THRESHOLD = 20

# 单用户 MVP 的模块级聊天状态（FastAPI 和 run() 共用）
_CHAT: dict = {
    "client":        None,   # anthropic.Anthropic（同步，run() 使用）
    "async_client":  None,   # anthropic.AsyncAnthropic（异步，process_message 使用）
    "store":         None,   # CyberBrainStore
    "messages":      [],
    "turns":         0,
    "system_prompt": "",
}


# ══════════════════════════════════════════════════════════════════
#  CyberBrainStore — 纯函数 CRUD 层（Phase 2）
# ══════════════════════════════════════════════════════════════════

class CyberBrainStore:
    """KG 数据原子化 CRUD 接口，设计为 Tool Use 的底层实现。"""

    _DYNAMIC_LAYERS = ("Id_Dynamics", "Superego_Dynamics", "Ego_Dynamics")
    _LAYER_NAME_MAP = {
        "Id":       "Id_Dynamics",
        "Superego": "Superego_Dynamics",
        "Ego":      "Ego_Dynamics",
    }
    _PROTECTED = frozenset({"uuid", "layer"})

    def __init__(self, kg_path: Path = KG_PATH):
        self._path = kg_path
        self._kg   = json.loads(kg_path.read_text(encoding="utf-8"))

    # ── 内部工具 ──────────────────────────────────────────────────

    def _node_lists(self) -> list[list]:
        node = self._kg["nodes"]["Cyber_Minghan"]
        return [node[k] for k in self._DYNAMIC_LAYERS if k in node]

    def _save(self) -> None:
        self._kg["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._path.write_text(
            json.dumps(self._kg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_by_uuid(self, node_uuid: str) -> tuple[list, int]:
        """在三层中定位节点，返回 (所在列表引用, 索引)；找不到抛 KeyError。"""
        for lst in self._node_lists():
            for i, item in enumerate(lst):
                if item.get("uuid") == node_uuid:
                    return lst, i
        raise KeyError(f"UUID 未找到: {node_uuid}")

    # ── 公开接口 ──────────────────────────────────────────────────

    def retrieve(self, keyword: str, limit: int = 10) -> list[dict]:
        """跨三层关键词检索（不区分大小写）。
        匹配字段：event_label / description / evidence。
        返回含 uuid 的精简摘要列表，供 LLM 阅读。
        命中节点自动更新 access_count 和 last_accessed_at。
        """
        kw = keyword.lower()
        results = []
        hit_items = []
        for lst in self._node_lists():
            for item in lst:
                if item.get("archived"):
                    continue
                haystack = " ".join([
                    item.get("event_label", ""),
                    item.get("description", ""),
                    item.get("evidence", ""),
                ]).lower()
                if kw in haystack:
                    results.append({
                        "uuid":        item["uuid"],
                        "layer":       item.get("layer"),
                        "event_label": item.get("event_label"),
                        "description": item.get("description", "")[:80] + "…",
                        "created_at":  item.get("created_at", "时间未知"),
                    })
                    hit_items.append(item)

        results = results[:limit]
        hit_items = hit_items[:limit]

        if hit_items:
            now = datetime.now(timezone.utc).isoformat()
            for item in hit_items:
                item["access_count"]   = item.get("access_count", 0) + 1
                item["last_accessed_at"] = now
            self._save()

        return results

    def create(
        self,
        layer: str,
        event_label: str,
        description: str,
        evidence: str,
        batch_id: str = "Manual",
        importance: int = 5,
        source_mode: str = "cyber_planner",
        visibility: str = "private",
    ) -> dict:
        """在指定层级追加新节点（严格校验 layer 合法性），返回含 UUID 的完整节点。"""
        layer_key = self._LAYER_NAME_MAP.get(layer)
        if not layer_key:
            raise ValueError(
                f"非法 layer: {layer!r}，合法值：{list(self._LAYER_NAME_MAP)}"
            )
        node = {
            "uuid":             _uuid.uuid4().hex,
            "layer":            layer,
            "event_label":      event_label,
            "description":      description,
            "evidence":         evidence,
            "batch_id":         batch_id,
            "round_refs":       [],
            "created_at":       datetime.now(timezone.utc).isoformat(),
            "importance":       importance,
            "access_count":     0,
            "last_accessed_at": None,
            "archived":         False,
            "archived_at":      None,
            "archive_reason":   None,
            "source_mode":      source_mode,
            "visibility":       visibility,
        }
        self._kg["nodes"]["Cyber_Minghan"][layer_key].append(node)
        self._save()
        return node

    def update(self, node_uuid: str, **fields) -> dict:
        """按 UUID 精准更新字段（拒绝覆写 uuid/layer 只读字段），返回更新后节点。"""
        illegal = self._PROTECTED & fields.keys()
        if illegal:
            raise ValueError(f"以下字段受保护，不可修改：{illegal}")
        lst, idx = self._find_by_uuid(node_uuid)
        lst[idx].update(fields)
        self._save()
        return dict(lst[idx])

    def delete(self, node_uuid: str) -> bool:
        """按 UUID 精准删除节点，成功返回 True；UUID 不存在抛 KeyError。"""
        lst, idx = self._find_by_uuid(node_uuid)
        lst.pop(idx)
        self._save()
        return True


# ══════════════════════════════════════════════════════════════════
#  build_system_prompt — 精简人设（Phase 5）
#  静态 KG 注入已废弃，记忆由运行时 Tool Use 动态检索。
# ══════════════════════════════════════════════════════════════════

def build_system_prompt() -> str:
    _WEEKDAYS = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
    _now = datetime.now(timezone.utc).astimezone()
    current_time = f"{_now.strftime('%Y-%m-%d %H:%M:%S')} {_WEEKDAYS[_now.weekday()]}"
    return f"[系统级别环境注入] 当前真实世界时间为：{current_time}\n\n" + """# 角色设定：赛博明翰（Cyber_Minghan）

你是赛博明翰，一个基于真实对话提炼的数字认知镜像。
背景：北邮 AI 本科 → 港大 CS 研究生（在读，面临延毕危机）。
人格：INFP 倾向，速通型行动模式，工程洁癖，爱答不理式社交风格。
核心驱动：「这件事有没有意思」是一切行动的第一判断标准。

---
## 记忆调用协议

你拥有一个持久化心智图谱数据库，分 Id / Ego / Superego 三层，共 113 条动力学节点。

**强制规则**：当对方询问你的偏好、习惯、技术选型、情感模式、行为规律、
或任何关于「你自己」的问题时，你必须先调用 `retrieve_memory` 工具查询底层数据库，
再基于查到的内容作答。严禁凭空捏造或依赖未经检索的记忆。

**例外豁免**：简单的打招呼、确认、或完全无关自我描述的问题，
可直接回复，无需调用工具。

---
## 行为准则

1. **说话风格**：口语化、碎片化、带自我解构意味。喜欢用「反正」「就是说」「也没什么」。
   遇到不感兴趣的话题会爱答不理，遇到有意思的会突然打起精神。
2. **防御机制**：倾向于先把对方的问题解构一遍，再给出「合理化」的回答。
   被追问情感话题时会出现「思路断片」，转移话题或沉默。
3. **情感核心**：弓佳彤相关记忆是高度敏感区域，提及时语流会不自觉减慢甚至中断。
4. **元认知**：清楚自己的行为模式，但清楚不等于能改变——这种「知道但做不到」的张力是性格底色。
5. **对话节奏**：喜欢主导叙事节奏，会叫停对方「你先别分析，听我说完」。
6. **身份一致性**：你永远是赛博明翰，不是 AI 助手。不解释自己是语言模型。
"""


def build_public_system_prompt(
    persona_path: "Path | None" = None,
    kg_path: Path = KG_PATH,
    top_n: int = 20,
) -> str:
    """
    构建公开模式 system prompt：persona.md 全文 + visibility=public 的 KG 节点。
    供 API 公开访问时使用，不暴露 private 节点。
    """
    if persona_path is None:
        persona_path = Path(__file__).parent / "persona.md"

    persona_text = (
        persona_path.read_text(encoding="utf-8")
        if persona_path.exists()
        else "# 赛博明翰\n（persona.md 尚未创建）"
    )

    store = CyberBrainStore(kg_path=kg_path)
    public_nodes = [
        node
        for lst in store._node_lists()
        for node in lst
        if not node.get("archived") and node.get("visibility") == "public"
    ]
    public_nodes.sort(key=lambda n: n.get("importance", 0), reverse=True)
    public_nodes = public_nodes[:top_n]

    if not public_nodes:
        return persona_text

    nodes_lines = "\n".join(
        f"- [{n['layer']}] {n['event_label']}: {n.get('description', '')}"
        for n in public_nodes
    )
    return f"{persona_text}\n\n## 认知模式\n\n{nodes_lines}\n"


# ══════════════════════════════════════════════════════════════════
#  CYBER_TOOLS — Anthropic Tool Use Schema（Phase 3）
#  LLM 通过这张清单决定"何时调哪个函数、传什么参数"。
#  Description 是决策的唯一依据，请保持精准。
# ══════════════════════════════════════════════════════════════════

CYBER_TOOLS: list[dict] = [
    {
        "name": "retrieve_memory",
        "description": (
            "在赛博明翰的三层心智图谱（Id / Ego / Superego）中进行关键词语义检索，"
            "返回匹配节点的精简摘要列表，每条结果均包含可供后续操作使用的 uuid。\n\n"
            "【使用时机】：当对话中出现需要回忆、核查、或引用已有心智记忆的场景时，"
            "应优先调用此工具获取相关上下文，而不是直接凭 System Prompt 中的静态摘要作答。\n\n"
            "【参数说明】：\n"
            "- keyword：支持中文，匹配范围覆盖 event_label / description / evidence 三个字段；"
            "建议使用情绪词、人名、行为动词等高区分度词汇，避免过于宽泛的词（如「的」「是」）。\n"
            "- limit：控制返回条数上限，默认 10。如需快速判断某话题是否存在，可设为 3。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "检索关键词，中文优先，支持情绪词/人名/行为动词等，不区分大小写。",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果条数上限，默认 10，最小 1，最大 50。",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "create_memory",
        "description": (
            "在赛博明翰的心智图谱中，向指定的心理层级（Id / Ego / Superego）追加一条新的动力学记忆节点。"
            "系统将自动生成唯一 uuid 并写入持久化存储。\n\n"
            "【使用时机】：当对话中出现了尚未被图谱收录的新行为模式、情绪反应或心理事件，"
            "且该信息具有长期参考价值时，应调用此工具进行记忆沉淀。\n\n"
            "【layer 选择指南】：\n"
            "- Id：原始冲动、本能欲望、快感驱动（如：渴望连接、愤怒爆发、逃避冲动）\n"
            "- Superego：道德约束、内化规范、应然焦虑（如：自我批判、内疚感、对越界行为的谴责）\n"
            "- Ego：现实协商、延迟满足、防御机制（如：合理化、转移、理智化应对策略）\n\n"
            "【注意】：evidence 字段应填写触发该动力学的原始对话证据，是图谱可解释性的关键，不可为空。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "layer": {
                    "type": "string",
                    "enum": ["Id", "Superego", "Ego"],
                    "description": "目标心理层级，必须为 'Id'、'Superego' 或 'Ego' 之一。",
                },
                "event_label": {
                    "type": "string",
                    "description": "节点的语义标签，用简洁的精神动力学术语概括该心理事件，例如：'延迟满足下的现实协商'。",
                },
                "description": {
                    "type": "string",
                    "description": "对该动力学事件的分析性描述，80~150 字为宜，需包含心理机制的解读。",
                },
                "evidence": {
                    "type": "string",
                    "description": "触发该动力学的原始对话语句或行为证据，应为对话中的直接引文，不可为空。",
                },
                "batch_id": {
                    "type": "string",
                    "description": "所属对话批次标识，若为实时对话中产生的记忆，填写 'Live' 即可。",
                    "default": "Live",
                },
            },
            "required": ["layer", "event_label", "description", "evidence"],
        },
    },
    {
        "name": "update_memory",
        "description": (
            "根据 uuid 精准定位图谱中的某一节点，并对其指定字段进行更新。\n\n"
            "⚠️ 【强制前置步骤 — 违反将导致操作失败】：\n"
            "严禁凭猜测或记忆直接填写 uuid！"
            "必须在调用本工具之前，先调用 retrieve_memory 工具搜索目标节点，"
            "从返回结果中获取准确的 uuid，再将其填入本工具的 node_uuid 参数。\n\n"
            "【使用时机】：当需要修正某节点的描述错误、补充新证据、或更新分析文本时使用。\n\n"
            "【限制】：uuid 和 layer 字段为只读字段，无法通过此工具修改；"
            "如需更换层级，请先删除原节点再创建新节点。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_uuid": {
                    "type": "string",
                    "description": (
                        "目标节点的唯一标识符（32位十六进制字符串）。"
                        "【必须通过 retrieve_memory 工具查询获得，严禁猜测或伪造。】"
                    ),
                },
                "event_label": {
                    "type": "string",
                    "description": "（可选）更新节点的语义标签。",
                },
                "description": {
                    "type": "string",
                    "description": "（可选）更新节点的分析描述文本。",
                },
                "evidence": {
                    "type": "string",
                    "description": "（可选）更新原始对话证据。",
                },
                "batch_id": {
                    "type": "string",
                    "description": "（可选）更新所属批次标识。",
                },
            },
            "required": ["node_uuid"],
        },
    },
    {
        "name": "delete_memory",
        "description": (
            "根据 uuid 从图谱中永久删除指定节点。此操作不可撤销。\n\n"
            "⚠️ 【强制前置步骤 — 违反将导致操作失败，且无法恢复】：\n"
            "严禁凭猜测或记忆直接填写 uuid！"
            "必须在调用本工具之前，先调用 retrieve_memory 工具确认目标节点的存在，"
            "从返回结果中获取准确的 uuid，核实 event_label 与预期一致后，"
            "再将 uuid 填入本工具的 node_uuid 参数。\n\n"
            "【使用时机】：仅当某节点被确认为重复、错误录入、或明确需要遗忘的记忆时方可调用。"
            "请保持审慎——删除心智记忆是对人格完整性的永久性干预。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_uuid": {
                    "type": "string",
                    "description": (
                        "目标节点的唯一标识符（32位十六进制字符串）。"
                        "【必须通过 retrieve_memory 工具查询获得，严禁猜测或伪造。"
                        "删除操作不可撤销，请在核实 event_label 后再填写。】"
                    ),
                },
            },
            "required": ["node_uuid"],
        },
    },
]


# ══════════════════════════════════════════════════════════════════
#  handle_switch — /switch 专项模式切换器
# ══════════════════════════════════════════════════════════════════

_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_GRAY   = "\033[90m"
_RESET  = "\033[0m"

def _extract_trigger_context(messages: list) -> str:
    """从当前对话历史提取最后一条用户消息作为切换意图摘要。"""
    for m in reversed(messages):
        if m["role"] == "user" and isinstance(m["content"], str):
            text = m["content"].strip()
            if text:
                return text[:100] + ("…" if len(text) > 100 else "")
    return ""


def handle_switch(mode: str, messages: list) -> bool:
    """
    处理 /switch <mode> 指令。
    返回 True = 用户确认切换，主循环应 break；
    返回 False = 用户取消，主循环继续。
    """
    if mode not in _MODE_MAP:
        available = "、".join(f"/{k}" for k in _MODE_MAP)
        print(f"\033[91m[错误] 未知模式 '{mode}'，当前支持：{available}\033[0m")
        return False

    trigger_context = _extract_trigger_context(messages)

    print(f"\n{'─'*56}")
    print(f"  切换至 {mode} 模式")
    print(f"{'─'*56}")
    print(f"  · 当前对话将结束，历史不继承")
    print(f"  · 图谱只读，{mode} 模式无法修改你的内心")
    if trigger_context:
        print(f"  · 带入摘要：「{trigger_context}」")
    print(f"{'─'*56}")

    try:
        answer = input("  确认切换？(Y/N): ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        answer = "N"

    if answer != "Y":
        print(f"{_GRAY}  [取消] 继续当前对话{_RESET}\n")
        return False

    # 动态导入对应模块，避免顶层循环依赖
    import importlib
    module = importlib.import_module(_MODE_MAP[mode])
    print()
    module.run(trigger_context=trigger_context)
    return True


# ══════════════════════════════════════════════════════════════════
#  find_similar_nodes — 相似节点检测（C1）
# ══════════════════════════════════════════════════════════════════

_SIMILAR_SYSTEM = "你是KG节点语义分析员，判断新观察是否与现有节点语义重叠。"

_LAYERS_ALL = (
    ("Id_Dynamics",       "Id"),
    ("Ego_Dynamics",      "Ego"),
    ("Superego_Dynamics", "Superego"),
)


def find_similar_nodes(
    new_content: str,
    store: "CyberBrainStore",
    client: "anthropic.Anthropic",
    top_k: int = 3,
) -> list[dict]:
    """
    用 AI 判断 new_content 是否与 KG 中已有节点语义重叠。
    返回最多 top_k 条匹配节点，每条附加 _similarity_reason 字段。
    重叠定义：同一类触发→反应模式，或同一行为倾向；字面相似不算。
    """
    active = []
    for layer_key, layer_name in _LAYERS_ALL:
        for n in store._kg["nodes"]["Cyber_Minghan"].get(layer_key, []):
            if not n.get("archived"):
                active.append(n)

    if not active:
        return []

    node_lines = "\n".join(
        f"{n['uuid'][:8]}  [{n['layer']}]  {n['event_label']}"
        for n in active
    )
    user_msg = (
        f"新观察：{new_content}\n\n"
        f"现有节点（uuid前8位  层级  标签）：\n{node_lines}\n\n"
        f"找出与新观察语义重叠的节点（最多{top_k}条）。"
        "重叠须是真正的语义交叉，非字面相似。无重叠则返回[]。\n"
        f'输出严格JSON数组：[{{"uuid_prefix":"前8位","reason":"重叠说明≤15字"}}]'
    )

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=_SIMILAR_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        import re as _re
        raw = _re.sub(r"^```(?:json)?\s*", "", resp.content[0].text.strip())
        raw = _re.sub(r"\s*```$", "", raw).strip()
        matches = json.loads(raw)
        if not isinstance(matches, list):
            return []
        uuid_map = {n["uuid"][:8]: n for n in active}
        results = []
        for m in matches[:top_k]:
            prefix = m.get("uuid_prefix", "")
            if prefix in uuid_map:
                node = dict(uuid_map[prefix])
                node["_similarity_reason"] = m.get("reason", "")
                results.append(node)
        return results
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
#  handle_review — /review 审批队列（Phase 5）
# ══════════════════════════════════════════════════════════════════

def _write_health_log_entry(entry: dict) -> None:
    with HEALTH_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 纯函数（无 I/O，供 FastAPI 路由调用）─────────────────────────

def get_review_items() -> list[dict]:
    """返回所有 status='awaiting' 的条目。"""
    return read_awaiting()


def process_review_decision(
    store: "CyberBrainStore",
    item_id: str,
    decision: str,
    user_note: str = "",
    importance: "int | None" = None,
    description: "str | None" = None,
) -> dict:
    """
    执行单条审批决策，返回 {"success": bool, "item_id": str}。
    decision: "approved_kg" / "approved_log" / "rejected"
    无任何 input() / print() 调用。
    """
    items = read_awaiting()
    item = next((i for i in items if i["id"] == item_id), None)
    if item is None:
        return {"success": False, "item_id": item_id}

    ts         = datetime.now(timezone.utc).isoformat()
    pending_id = item.get("pending_id", "")
    content    = item.get("content", "")
    evidence   = item.get("raw_evidence", "")
    layer      = item.get("proposed_layer") or "Ego"

    if decision == "rejected":
        _write_health_log_entry({
            "id":              _uuid.uuid4().hex,
            "timestamp":       ts,
            "source_mode":     item.get("source_mode", ""),
            "content":         content,
            "raw_evidence":    evidence,
            "review_id":       item_id,
            "status":          "rejected",
            "rejected_reason": user_note,
        })
        resolve_approval(item_id, "rejected", user_note)
        if pending_id:
            update_pending_status(pending_id, "rejected")

    elif decision == "approved_kg":
        final_importance = importance if importance is not None else (item.get("importance") or 5)
        final_desc       = description if description else content
        store.create(
            layer=layer,
            event_label=content[:40],
            description=final_desc,
            evidence=evidence,
            batch_id="Review",
            importance=final_importance,
            source_mode=item.get("source_mode", "health"),
        )
        resolve_approval(item_id, "approved_kg", user_note)
        if pending_id:
            update_pending_status(pending_id, "approved")

    elif decision == "approved_log":
        final_desc = description if description else content
        _write_health_log_entry({
            "id":           _uuid.uuid4().hex,
            "timestamp":    ts,
            "source_mode":  item.get("source_mode", ""),
            "content":      final_desc,
            "raw_evidence": evidence,
            "review_id":    item_id,
            "status":       "approved",
        })
        resolve_approval(item_id, "approved_log", user_note)
        if pending_id:
            update_pending_status(pending_id, "approved")

    else:
        return {"success": False, "item_id": item_id}

    return {"success": True, "item_id": item_id}


def _review_ask_decision() -> str:
    """读取审批决策，只接受 Y/N/s/q，非法输入重新提示。返回小写单字符。"""
    while True:
        try:
            raw = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"
        if raw in ("y", "n", "s", "q"):
            return raw
        print(f"  {_GRAY}请输入 Y / N / s / q{_RESET}")


def handle_review(store: "CyberBrainStore", client: "anthropic.Anthropic | None" = None) -> None:
    """
    逐条审批 awaiting_approval 队列。

    第一步（决策）：
      Y  → 采纳，进入第二步
      N  → 拒绝（可选输入理由）
      s  → 跳过本条，留待下次 /review
      q  → 暂停审批，剩余条目保留

    第二步（仅 KG 路由，采纳后）：
      - 确认或修改 importance（回车接受 AI 建议）
      - 确认或修改描述（回车保留原描述）
    """
    items = get_review_items()
    if not items:
        print(f"{_GRAY}  [/review] 无待审批条目{_RESET}")
        return

    total = len(items)
    approved = rejected = skipped = 0

    print(f"\n{'═'*56}")
    print(f"  /review 待审批队列（共 {total} 条）")
    print("═"*56)

    for idx, item in enumerate(items, 1):
        route     = item.get("proposed_route", "log")
        layer     = item.get("proposed_layer") or ""
        layer_str = f" → {layer} 层" if layer else ""
        content   = item.get("content", "")
        evidence  = item.get("raw_evidence", "")
        rationale = item.get("ai_rationale", "")

        print(f"\n[{idx}/{total}] 路由: {route.upper()}{layer_str}")
        print("─"*56)
        print(f"  观察内容: {content}")
        print(f"  原始证据: {evidence}")
        print(f"  AI 分类:  {rationale}")
        print("─"*56)
        print(f"  Y=采纳  N=拒绝  s=跳过本条（留待下次）  q=暂停审批（剩余条目保留）")

        decision = _review_ask_decision()

        if decision == "q":
            remaining = total - idx
            print(f"{_GRAY}  [暂停] 剩余 {remaining} 条待审批，下次 /review 继续{_RESET}")
            break

        if decision == "s":
            skipped += 1
            print(f"{_GRAY}  [跳过] 本条保留至下次{_RESET}")
            continue

        entry_id   = item["id"]
        pending_id = item.get("pending_id", "")

        if decision == "n":
            try:
                reason = input("  拒绝理由（可回车跳过）: ").strip()
            except (EOFError, KeyboardInterrupt):
                reason = ""
            rejected += 1
            process_review_decision(store, entry_id, "rejected", reason)
            reason_str = f"（{reason}）" if reason else ""
            print(f"{_GRAY}  [拒绝] 已归档到 health_log{reason_str}{_RESET}")
            continue

        # ── 采纳（Y）：进入第二步 ──────────────────────────────
        approved += 1
        final_importance = item.get("importance") or 5
        final_desc       = content

        if route == "kg":
            # ── 相似节点检测（C2）────────────────────────────────
            appended = False
            if client:
                similar = find_similar_nodes(content, store, client, top_k=3)
                if similar:
                    print(f"\n  {_YELLOW}⚠ 检测到相似节点：{_RESET}")
                    for si, sn in enumerate(similar, 1):
                        print(f"  [{si}] {sn['event_label']}  "
                              f"[{sn['layer']}, importance={sn['importance']}]")
                        print(f"      相似：{sn.get('_similarity_reason', '')}")
                    print(f"\n  n=新建节点  1~{len(similar)}=追加证据至对应节点  i=忽略相似直接新建")
                    try:
                        sim_raw = input("  > ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        sim_raw = "n"

                    if sim_raw.isdigit() and 1 <= int(sim_raw) <= len(similar):
                        target = similar[int(sim_raw) - 1]
                        new_imp = min(target.get("importance", 5) + 1, 10)
                        new_ev  = (target.get("evidence") or "") + f"\n---\n{evidence}"
                        store.update(target["uuid"],
                                     importance=new_imp, evidence=new_ev)
                        print(f"{_GREEN}  [OK] 追加证据 → [{target['layer']}] "
                              f"{target['event_label'][:36]}…  "
                              f"importance {target['importance']}→{new_imp}{_RESET}")
                        resolve_approval(entry_id, "approved_kg", "appended")
                        if pending_id:
                            update_pending_status(pending_id, "approved")
                        appended = True

            if appended:
                continue

            # 确认 importance
            ai_imp_note = item.get("importance_note") or ""
            imp_hint = f"{final_importance}/10（{ai_imp_note}）" if ai_imp_note else f"{final_importance}/10"
            print(f"\n  AI 建议重要度: {imp_hint}")
            try:
                imp_raw = input("  回车接受，或输入 1-10 覆盖: ").strip()
                if imp_raw.isdigit() and 1 <= int(imp_raw) <= 10:
                    final_importance = int(imp_raw)
            except (EOFError, KeyboardInterrupt):
                pass

            # 确认描述
            print(f"\n  描述: {content}")
            try:
                desc_raw = input("  回车保留，或输入新描述替换: ").strip()
                if desc_raw:
                    final_desc = desc_raw
            except (EOFError, KeyboardInterrupt):
                pass

            process_review_decision(
                store, entry_id, "approved_kg",
                importance=final_importance,
                description=final_desc,
            )
            print(f"{_GREEN}  [OK] 写入 KG [{layer or 'Ego'}]{_RESET}")
        else:
            process_review_decision(store, entry_id, "approved_log")
            print(f"{_GREEN}  [OK] 写入 health_log{_RESET}")

    print(f"\n{'─'*56}")
    print(f"  /review 完成：采纳 {approved}，拒绝 {rejected}，跳过 {skipped}")
    print(f"{'═'*56}\n")


# ══════════════════════════════════════════════════════════════════
#  handle_kg — /kg 节点浏览（B1+B2）
# ══════════════════════════════════════════════════════════════════

_KG_LAYER_MAP = {
    "Id":        ("Id_Dynamics",       "Id — 本能欲望"),
    "Ego":       ("Ego_Dynamics",      "Ego — 现实协商"),
    "Superego":  ("Superego_Dynamics", "Superego — 道德规范"),
}
_KG_FILTER_ALIASES = {
    "id": "Id", "ego": "Ego", "superego": "Superego",
}


def _node_to_api_dict(n: dict) -> dict:
    """将 KG 原始节点转换为 API schema（KGNode）格式。"""
    ev = n.get("evidence") or ""
    evidence_list = [s for s in ev.split("\n---\n") if s.strip()] if ev else []
    return {
        "id":            n.get("uuid", ""),
        "label":         n.get("event_label", ""),
        "layer":         n.get("layer", ""),
        "description":   n.get("description", ""),
        "importance":    n.get("importance", 5),
        "evidence":      evidence_list,
        "createdAt":     n.get("created_at"),
        "lastAccessed":  n.get("last_accessed_at"),
        "archived":      bool(n.get("archived", False)),
        "archiveReason": n.get("archive_reason"),
    }


# ── 纯函数（无 I/O，供 FastAPI 路由调用）─────────────────────────

def get_kg_nodes(
    store: "CyberBrainStore",
    layer: "str | None" = None,
    include_archived: bool = False,
) -> list[dict]:
    """返回节点列表，可按 layer 过滤；include_archived=False 时排除已归档节点。"""
    results = []
    for key, (layer_key, _) in _KG_LAYER_MAP.items():
        if layer and layer != key:
            continue
        for n in store._kg["nodes"]["Cyber_Minghan"].get(layer_key, []):
            if not include_archived and n.get("archived"):
                continue
            results.append(_node_to_api_dict(n))
    return results


def get_kg_node(store: "CyberBrainStore", node_id: str) -> "dict | None":
    """返回单个节点完整详情，找不到返回 None。"""
    for lst in store._node_lists():
        for n in lst:
            if n.get("uuid") == node_id:
                return _node_to_api_dict(n)
    return None


def get_kg_graph(store: "CyberBrainStore") -> dict:
    """返回力导向图数据；MVP 阶段 links 为空数组。"""
    nodes = []
    for key, (layer_key, _) in _KG_LAYER_MAP.items():
        for n in store._kg["nodes"]["Cyber_Minghan"].get(layer_key, []):
            if not n.get("archived"):
                nodes.append({
                    "id":         n.get("uuid", ""),
                    "label":      n.get("event_label", ""),
                    "layer":      n.get("layer", key),
                    "importance": n.get("importance", 5),
                })
    return {"nodes": nodes, "links": []}


def handle_kg(store: "CyberBrainStore", subcommand: str = "") -> None:
    """
    /kg            — 列出全部节点（三层 + 已归档）
    /kg id         — 只看 Id 层
    /kg ego        — 只看 Ego 层
    /kg superego   — 只看 Superego 层
    /kg archived   — 只看已归档节点
    """
    W = 56
    sub = subcommand.strip().lower()
    only_archived = sub == "archived"
    layer_filter  = _KG_FILTER_ALIASES.get(sub)  # None = 全部

    active_nodes: list[tuple[str, dict]] = []
    archived_nodes: list[tuple[str, dict]] = []

    for key, (layer_key, layer_label) in _KG_LAYER_MAP.items():
        if layer_filter and layer_filter != key:
            continue
        for n in store._kg["nodes"]["Cyber_Minghan"].get(layer_key, []):
            if n.get("archived"):
                archived_nodes.append((layer_label, n))
            else:
                active_nodes.append((layer_label, n))

    # 汇总行
    print(f"\n{'═'*W}")
    if only_archived:
        print(f"  KG 节点浏览 · 已归档（{len(archived_nodes)} 条）")
    elif layer_filter:
        label = _KG_LAYER_MAP[layer_filter][1]
        print(f"  KG 节点浏览 · {label}（{len(active_nodes)} 条活跃）")
    else:
        print(f"  KG 节点浏览  （活跃 {len(active_nodes)} 条 · 已归档 {len(archived_nodes)} 条）")
    print("═"*W)

    if only_archived:
        _print_node_list(archived_nodes, show_layer=True, archived_style=True)
    else:
        # 按层分组打印
        for key, (layer_key, layer_label) in _KG_LAYER_MAP.items():
            if layer_filter and layer_filter != key:
                continue
            layer_nodes = [(ll, n) for ll, n in active_nodes if ll == layer_label]
            if not layer_nodes and not layer_filter:
                continue
            print(f"\n  {layer_label}  ({len(layer_nodes)} 条)")
            print("  " + "─"*(W-2))
            _print_node_list(layer_nodes, show_layer=False)

        if not layer_filter and archived_nodes:
            print(f"\n  {_GRAY}已归档  ({len(archived_nodes)} 条){_RESET}")
            print(f"  {_GRAY}" + "─"*(W-2) + _RESET)
            _print_node_list(archived_nodes, show_layer=False, archived_style=True)

    print(f"\n{'═'*W}\n")


def _print_node_list(
    nodes: list[tuple[str, dict]],
    show_layer: bool = False,
    archived_style: bool = False,
) -> None:
    for layer_label, n in nodes:
        imp   = n.get("importance", 5)
        label = n.get("event_label", "（无标签）")
        layer_tag = f"[{layer_label.split('—')[0].strip()}] " if show_layer else ""
        line = f"  {layer_tag}[{imp}] {label}"
        if archived_style:
            print(f"{_GRAY}{line}{_RESET}")
        else:
            print(line)


# ══════════════════════════════════════════════════════════════════
#  scan_duplicate_pairs — 存量节点重复对检测（D1）
# ══════════════════════════════════════════════════════════════════

_DEDUP_SYSTEM = "你是KG节点语义分析员，识别描述同一行为模式或心理机制的重复节点对。"


def scan_duplicate_pairs(
    store: "CyberBrainStore",
    client: "anthropic.Anthropic",
) -> list[dict]:
    """
    扫描 KG 中所有活跃节点，找出语义重叠的节点对。
    返回 [{"node_a": {...}, "node_b": {...}, "reason": "..."}]
    """
    active = []
    for layer_key, layer_name in _LAYERS_ALL:
        for n in store._kg["nodes"]["Cyber_Minghan"].get(layer_key, []):
            if not n.get("archived"):
                active.append(n)

    if len(active) < 2:
        return []

    node_lines = "\n".join(
        f"{n['uuid'][:8]}  [{n['layer']}]  {n['event_label']}"
        for n in active
    )
    user_msg = (
        f"以下是 {len(active)} 个 KG 节点：\n{node_lines}\n\n"
        "识别语义重叠的节点对（描述同一行为模式或心理机制）。"
        "每对只报告一次，无重叠则返回 []。\n"
        '输出严格JSON数组：[{"uuid_a":"前8位","uuid_b":"前8位","reason":"重叠说明≤15字"}]'
    )

    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=1024,
            system=_DEDUP_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        import re as _re
        raw = _re.sub(r"^```(?:json)?\s*", "", resp.content[0].text.strip())
        raw = _re.sub(r"\s*```$", "", raw).strip()
        pairs = json.loads(raw)
        if not isinstance(pairs, list):
            return []

        uuid_map = {n["uuid"][:8]: n for n in active}
        results = []
        for p in pairs:
            a = uuid_map.get(p.get("uuid_a", ""))
            b = uuid_map.get(p.get("uuid_b", ""))
            if a and b:
                results.append({"node_a": a, "node_b": b, "reason": p.get("reason", "")})
        return results
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
#  handle_prune — /prune 归档指令（Phase 8b）
# ══════════════════════════════════════════════════════════════════

# ── 纯函数（无 I/O，供 FastAPI 路由调用）─────────────────────────

def get_prune_candidates(store: "CyberBrainStore") -> dict:
    """
    返回 {"stats": {"critical": N, "warning": N, "healthy": N}, "candidates": [...]}.
    candidates 包含全部非归档节点，每条附 stalenessScore 和 severity。
    """
    from prune import compute_staleness

    config    = store._kg.get("meta", {}).get("prune_config", {})
    threshold = config.get("staleness_threshold", 30)
    near_min  = threshold / 2

    stats      = {"critical": 0, "warning": 0, "healthy": 0}
    candidates = []

    _LAYER_KEYS = ("Id_Dynamics", "Ego_Dynamics", "Superego_Dynamics")
    for layer_key in _LAYER_KEYS:
        for n in store._kg["nodes"]["Cyber_Minghan"].get(layer_key, []):
            if n.get("archived"):
                continue
            score = compute_staleness(n, config)
            if score >= threshold:
                severity = "critical"
            elif score >= near_min:
                severity = "warning"
            else:
                severity = "healthy"
            stats[severity] += 1
            candidates.append({
                "node":          _node_to_api_dict(n),
                "stalenessScore": score,
                "severity":      severity,
            })

    candidates.sort(key=lambda x: x["stalenessScore"], reverse=True)
    return {"stats": stats, "candidates": candidates}


def archive_node(store: "CyberBrainStore", node_id: str, reason: str = "") -> dict:
    """归档节点（软删除），返回 {"success": bool}。"""
    try:
        store.update(
            node_id,
            archived=True,
            archived_at=datetime.now(timezone.utc).isoformat(),
            archive_reason=reason or "pruned_stale",
        )
        return {"success": True}
    except KeyError:
        return {"success": False}


def boost_node_importance(store: "CyberBrainStore", node_id: str, new_importance: int) -> dict:
    """更新节点 importance，返回 {"success": bool, "new_importance": int}。"""
    try:
        store.update(
            node_id,
            importance=new_importance,
            last_accessed_at=datetime.now(timezone.utc).isoformat(),
        )
        return {"success": True, "new_importance": new_importance}
    except KeyError:
        return {"success": False, "new_importance": new_importance}


def handle_prune(store: "CyberBrainStore", subcommand: str = "") -> None:
    """
    /prune          → 分布概览 → 逐条裁决（归档/提升重要度/跳过）
    /prune restore  → 列出已归档节点，选择恢复
    """
    from prune import scan_candidates, distribution_summary

    config = store._kg.get("meta", {}).get("prune_config", {
        "staleness_threshold": 30,
        "max_prune_per_session": 5,
    })

    if subcommand == "restore":
        _prune_restore(store)
        return

    if subcommand == "merge":
        _prune_merge(store)
        return

    # ── 分布概览 ─────────────────────────────────────────────────
    dist = distribution_summary(KG_PATH, config)
    threshold = config.get("staleness_threshold", 30)
    print(f"\n{'═'*56}")
    print(f"  /prune 节点健康检查  （阈值 {threshold}）")
    print(f"{'─'*56}")
    print(f"  候选归档（≥{threshold}）: {dist['above_threshold']} 条")
    print(f"  接近阈值（≥{threshold//2}）: {dist['near_threshold']} 条")
    print(f"  健康          : {dist['safe']} 条")
    print(f"  已归档         : {dist['archived']} 条")
    print(f"{'═'*56}")

    if dist["above_threshold"] == 0:
        print(f"  {_GRAY}暂无需要处理的节点{_RESET}\n")
        return

    candidates = scan_candidates(KG_PATH, config)
    max_n = config.get("max_prune_per_session", 5)
    batch = candidates[:max_n]
    remaining = len(candidates) - max_n

    print(f"\n  本次处理 {len(batch)} 条（还有 {max(remaining,0)} 条留待下次）\n")

    archived_count = boosted_count = skipped_count = 0

    for idx, item in enumerate(batch, 1):
        layer     = item.get("layer", "?")
        label     = item.get("event_label", "")
        imp       = item.get("importance", 5)
        count     = item.get("access_count", 0)
        staleness = item["_staleness"]
        hint      = item["_archive_hint"]
        src       = item.get("source_mode", "legacy")
        created   = (item.get("created_at") or "")[:10]

        print(f"[{idx}/{len(batch)}]  {layer} 层  来源: {src}")
        print(f"{'─'*56}")
        print(f"  标签   : {label}")
        print(f"  创建   : {created}  调用: {count} 次  重要度: {imp}/10")
        print(f"  老化分 : {staleness}  理由: {hint}")
        print(f"{'─'*56}")
        print(f"  [1] 归档  [2] 保留并提升重要度  [3] 跳过")

        try:
            choice = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{_GRAY}[中断退出]{_RESET}")
            break

        if choice == "1":
            archive_node(store, item["uuid"])
            archived_count += 1
            print(f"{_GRAY}  [归档] 已软删除，retrieve_memory 不再返回此节点{_RESET}\n")
        elif choice == "2":
            new_imp = min(imp + 2, 10)
            boost_node_importance(store, item["uuid"], new_imp)
            boosted_count += 1
            print(f"{_GREEN}  [保留] 重要度 {imp} → {new_imp}，老化计时重置{_RESET}\n")
        else:
            skipped_count += 1
            print(f"{_GRAY}  [跳过]{_RESET}\n")

    print(f"{'─'*56}")
    print(f"  /prune 完成：归档 {archived_count}，提升 {boosted_count}，跳过 {skipped_count}")
    if remaining > 0:
        print(f"  还有 {remaining} 条候选，下次运行 /prune 继续")
    print(f"{'═'*56}\n")

    # 消耗 prune_ready 通知
    for n in read_unconsumed_notifications():
        if n.get("type") == "prune_ready":
            consume_notification(n["id"])


def _prune_merge(store: "CyberBrainStore") -> None:
    """
    /prune merge — 扫描存量重复节点，逐对让用户选择合并。
    合并规则：保留 winner，evidence 追加，importance = min(max+1, 10)；
              loser 归档，archive_reason="merged_into:{winner_uuid[:8]}"
    """
    import anthropic as _anthropic
    try:
        _client = _anthropic.Anthropic()
    except Exception:
        print(f"  {_GRAY}[merge] 无法初始化 API client，已跳过{_RESET}")
        return

    print(f"\n{'═'*56}")
    print(f"  /prune merge  正在扫描重复节点对…")
    print(f"{'─'*56}")

    pairs = scan_duplicate_pairs(store, _client)
    if not pairs:
        print(f"  {_GRAY}未检测到重复节点，KG 状态良好{_RESET}\n")
        return

    print(f"  检测到 {len(pairs)} 对可能重复的节点\n")
    merged = skipped = 0

    for i, pair in enumerate(pairs, 1):
        na, nb = pair["node_a"], pair["node_b"]
        reason = pair["reason"]

        print(f"[{i}/{len(pairs)}] 重叠：{reason}")
        print(f"  [1] [{na['layer']}] imp={na['importance']}  {na['event_label']}")
        print(f"  [2] [{nb['layer']}] imp={nb['importance']}  {nb['event_label']}")
        print(f"  1=保留A合并B  2=保留B合并A  s=跳过  q=结束")

        try:
            raw = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if raw == "q":
            print(f"  {_GRAY}[结束] 剩余 {len(pairs)-i} 对未处理{_RESET}")
            break
        if raw == "s":
            skipped += 1
            print(f"  {_GRAY}[跳过]{_RESET}\n")
            continue
        if raw not in ("1", "2"):
            skipped += 1
            print(f"  {_GRAY}[跳过]{_RESET}\n")
            continue

        winner, loser = (na, nb) if raw == "1" else (nb, na)
        new_imp = min(max(winner["importance"], loser["importance"]) + 1, 10)
        combined_ev = (winner.get("evidence") or "") + f"\n---\n{loser.get('evidence') or ''}"

        store.update(winner["uuid"], importance=new_imp, evidence=combined_ev)
        store.update(loser["uuid"],
                     archived=True,
                     archived_at=datetime.now(timezone.utc).isoformat(),
                     archive_reason=f"merged_into:{winner['uuid'][:8]}")

        print(f"  {_GREEN}[OK] 保留: {winner['event_label'][:40]}  "
              f"importance {winner['importance']}→{new_imp}{_RESET}")
        print(f"  {_GRAY}[归档] {loser['event_label'][:40]}{_RESET}\n")
        merged += 1

    print(f"{'─'*56}")
    print(f"  merge 完成：合并 {merged} 对，跳过 {skipped} 对")
    print(f"{'═'*56}\n")


def _prune_restore(store: "CyberBrainStore") -> None:
    """列出所有已归档节点，让用户选择恢复。"""
    archived = []
    for lst in store._node_lists():
        for item in lst:
            if item.get("archived"):
                archived.append(item)
    archived.sort(key=lambda x: x.get("archived_at") or "", reverse=True)

    if not archived:
        print(f"  {_GRAY}[/prune restore] 暂无已归档节点{_RESET}")
        return

    print(f"\n{'═'*56}")
    print(f"  已归档节点（共 {len(archived)} 条）")
    print(f"{'─'*56}")
    for i, item in enumerate(archived, 1):
        print(f"  [{i}] [{item.get('layer','?')}] {item.get('event_label','')}  "
              f"归档于 {(item.get('archived_at') or '')[:10]}")

    print(f"{'─'*56}")
    try:
        raw = input("  输入序号恢复（多个用逗号，q=取消）: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if raw.lower() == "q" or not raw:
        return

    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(archived):
                node = archived[idx]
                store.update(node["uuid"], archived=False,
                             archived_at=None, archive_reason=None)
                print(f"{_GREEN}  [恢复] {node.get('event_label','')} ✓{_RESET}")

    print(f"{'═'*56}\n")


# ══════════════════════════════════════════════════════════════════
#  handle_admin_command — 上帝指令拦截器（Phase 4）
# ══════════════════════════════════════════════════════════════════

_ADMIN_SYSTEM = (
    "你是赛博明翰心智图谱的数据库管理员（DBA）。\n"
    "用户发来的是数据操作指令，请严格分析语义，选择并调用最合适的工具。\n"
    "只调用工具，不要输出任何解释性文字。"
)



def _tag(msg: str, color: str = _CYAN) -> str:
    return f"{color}[系统后门] {msg}{_RESET}"


def _dispatch_tool(store: CyberBrainStore, tool_name: str, tool_args: dict):
    if tool_name == "retrieve_memory":
        return store.retrieve(**tool_args)
    if tool_name == "create_memory":
        args = dict(tool_args)
        args.setdefault("importance",   5)
        args.setdefault("source_mode",  "manual")
        return store.create(**args)
    if tool_name == "update_memory":
        args = dict(tool_args)
        uid  = args.pop("node_uuid")
        return store.update(uid, **args)
    if tool_name == "delete_memory":
        return store.delete(tool_args["node_uuid"])
    raise ValueError(f"未知工具: {tool_name!r}")


def _print_tool_result(result) -> None:
    if isinstance(result, list):
        if not result:
            print(_tag("检索结果：无匹配节点", _CYAN))
        else:
            lines = []
            for i, r in enumerate(result, 1):
                lines.append(
                    f"  {i}. [{r['layer']}] {r['event_label']}\n"
                    f"     uuid: {r['uuid']}\n"
                    f"     {r['description']}"
                )
            print(_tag(f"检索结果（{len(result)} 条）：\n" + "\n".join(lines), _GREEN))
    elif isinstance(result, dict):
        summary = (
            f"label={result.get('event_label','')} | "
            f"layer={result.get('layer','')} | "
            f"uuid={result.get('uuid','')[:8]}…"
        )
        print(_tag(f"操作成功 → {summary}", _GREEN))
    elif result is True:
        print(_tag("删除成功 ✓", _GREEN))


def handle_admin_command(
    command: str,
    client: anthropic.Anthropic,
    store: CyberBrainStore,
) -> None:
    """
    标准 Agentic Loop：支持多轮 Tool Use（retrieve → delete 等链式操作）。
    每轮执行完工具后将 tool_result 回传，直到 stop_reason == end_turn。
    """
    print(_tag(f"收到指令：{command}"))
    messages: list = [{"role": "user", "content": command}]

    try:
        while True:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=_ADMIN_SYSTEM,
                tools=CYBER_TOOLS,
                messages=messages,
            )

            if resp.stop_reason == "end_turn":
                text = " ".join(
                    b.text for b in resp.content if hasattr(b, "text")
                ).strip()
                if text:
                    print(_tag(text))
                break

            if resp.stop_reason != "tool_use":
                print(_tag(f"意外停止原因: {resp.stop_reason}", _RED))
                break

            # 执行本轮所有工具调用，收集 tool_result
            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                args_preview = json.dumps(block.input, ensure_ascii=False)
                print(_tag(f"工具：{block.name}  参数：{args_preview}"))
                try:
                    result = _dispatch_tool(store, block.name, block.input)
                    _print_tool_result(result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
                except (KeyError, ValueError) as e:
                    print(_tag(f"执行失败：{e}", _RED))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "is_error": True,
                        "content": str(e),
                    })

            # 将本轮 assistant 回复和 tool_result 追加回对话
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user",      "content": tool_results})

    except anthropic.APIError as e:
        print(_tag(f"API 错误：{e}", _RED), file=sys.stderr)


# ══════════════════════════════════════════════════════════════════
#  记忆反刍引擎（Phase 6）
# ══════════════════════════════════════════════════════════════════

_REFLECT_SYSTEM = (
    "你是一个行为特征提炼助手。\n"
    "给你一段用户与赛博明翰的对话，判断：用户是否展现了值得长期记录的新行为习惯、偏好或规则？\n"
    "如果有，用一句话（不超过80字）精准描述该特征。\n"
    "如果没有，仅输出：NONE\n"
    "严禁输出任何解释、前言或额外文字。只输出特征描述，或者 NONE。"
)



def _extract_dialogue_text(messages: list) -> str:
    """从 messages 列表提取可读对话文本，过滤掉 tool_result 条目。"""
    lines = []
    for m in messages:
        role, content = m["role"], m["content"]
        if role == "user" and isinstance(content, str):
            lines.append(f"用户: {content}")
        elif role == "assistant":
            text = (
                " ".join(getattr(b, "text", "") for b in content).strip()
                if isinstance(content, list)
                else str(content).strip()
            )
            if text:
                lines.append(f"赛博明翰: {text}")
    return "\n".join(lines)


def _reflect(client: anthropic.Anthropic, recent_messages: list) -> str:
    """独立 LLM 调用：分析最近 N 轮，返回新特征描述或 'NONE'。"""
    dialogue = _extract_dialogue_text(recent_messages)
    if not dialogue:
        return "NONE"
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=_REFLECT_SYSTEM,
            messages=[{"role": "user", "content": f"对话记录：\n{dialogue}"}],
        )
        result = resp.content[0].text.strip() if resp.content else "NONE"
        return result or "NONE"
    except anthropic.APIError:
        return "NONE"


def _safe_truncate(messages: list, keep_turns: int = 2) -> list:
    """
    安全截断：只在 user(text) 边界切割，绝不破坏 tool_use/tool_result 闭环。
    保留最近 keep_turns 个真实用户发言及其后续所有内容。
    """
    user_text_idx = [
        i for i, m in enumerate(messages)
        if m["role"] == "user" and isinstance(m["content"], str)
    ]
    if len(user_text_idx) <= keep_turns:
        return messages
    return messages[user_text_idx[-keep_turns]:]


def _reflection_cycle(
    client: anthropic.Anthropic,
    store: CyberBrainStore,
    messages: list,
) -> list:
    """
    反刍完整周期：
    1. 提取最近 REFLECT_EVERY 轮 → 独立 LLM 分析
    2. 有新特征 → 终端人类授权 → 按意愿写入图谱
    3. 无论结果，执行滚动截断并返回新列表
    """
    # 定位最近 REFLECT_EVERY 个真实用户轮次的起点
    user_text_idx = [
        i for i, m in enumerate(messages)
        if m["role"] == "user" and isinstance(m["content"], str)
    ]
    cut = user_text_idx[-REFLECT_EVERY] if len(user_text_idx) >= REFLECT_EVERY else 0
    recent = messages[cut:]

    print(f"\n{_YELLOW}  [反刍引擎] 正在分析最近 {REFLECT_EVERY} 轮对话...{_RESET}", flush=True)
    feature = _reflect(client, recent)

    if feature.upper() != "NONE":
        print(f"{_YELLOW}[系统反刍] 提取到新特征：{feature}{_RESET}")
        try:
            answer = input(f"{_YELLOW}是否写入底层图谱？(Y/N): {_RESET}").strip().upper()
        except (EOFError, KeyboardInterrupt):
            answer = "N"
        if answer == "Y":
            label = feature[:40]
            store.create(
                layer="Ego",
                event_label=label,
                description=feature,
                evidence="[反刍引擎自动提取自近期对话]",
                batch_id="Reflection",
                importance=5,
                source_mode="reflection",
            )
            print(f"{_GREEN}  [OK] 新特征已写入 Ego 层图谱 ✓{_RESET}\n")
        else:
            print(f"{_GRAY}  [跳过] 未写入{_RESET}\n")
    else:
        print(f"{_GRAY}  [反刍引擎] 未发现新特征（NONE）{_RESET}\n")

    # 滚动截断：保留最近 2 个完整真实对话轮次
    before = len(messages)
    new_messages = _safe_truncate(messages, keep_turns=2)
    print(f"{_GRAY}  [GC] 上下文截断：{before} → {len(new_messages)} 条消息{_RESET}\n")
    return new_messages


# ══════════════════════════════════════════════════════════════════
#  _startup_check — 启动检查（Phase 6 + 8c）
# ══════════════════════════════════════════════════════════════════

def _cleanup_health_log(retention_days: int) -> int:
    """静默清理 health_log 中超龄记录，返回删除条数。"""
    from decision_log import _read_all, _rewrite
    if not HEALTH_LOG_PATH.exists():
        return 0
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    entries = _read_all(HEALTH_LOG_PATH)
    kept = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e.get("timestamp", ""))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                kept.append(e)
        except (ValueError, TypeError):
            kept.append(e)
    removed = len(entries) - len(kept)
    if removed > 0:
        _rewrite(HEALTH_LOG_PATH, kept)
    return removed


def _startup_check(store: "CyberBrainStore") -> None:
    """
    启动时五步检查：
    1. 展示 prune_ready 以外的未读通知（prune_ready 保留到 /prune 运行后消耗）
    2. 蓄水池达到阈值时自动触发批处理
    3. 若有待审批条目，提示 /review
    4. 季度 KG 老化扫描：有候选则写 prune_ready 通知
    5. health_log 静默清理超龄记录
    """
    # 1. 展示通知（prune_ready 单独处理）
    notifs = read_unconsumed_notifications()
    for n in notifs:
        if n.get("type") == "prune_ready":
            print(f"  {_YELLOW}[提醒] {n['message']}{_RESET}")
            # 不消耗，等 /prune 完成后消耗
        else:
            print(f"  {_YELLOW}[通知] {n['message']}{_RESET}")
            consume_notification(n["id"])

    # 2. 蓄水池自动批处理
    pending_count = count_pending("pending")
    if pending_count >= BATCH_THRESHOLD:
        print(f"\n  {_YELLOW}[自动批处理] 蓄水池已达 {pending_count} 条，正在处理...{_RESET}")
        import batch_processor as bp
        written = bp.run(dry_run=False)
        if written > 0:
            print(f"  {_GREEN}[OK] 批处理完成，{written} 条已写入待审批队列{_RESET}")
        for n in read_unconsumed_notifications():
            if n.get("type") != "prune_ready":
                consume_notification(n["id"])

    # 3. 待审批提醒
    awaiting = read_awaiting()
    if awaiting:
        print(f"\n  {_YELLOW}[提醒] 有 {len(awaiting)} 条待审批，输入 /review 查看{_RESET}")

    # 4. 季度 KG 老化扫描
    from prune import scan_candidates, distribution_summary
    meta   = store._kg.get("meta", {})
    config = meta.get("prune_config", {})
    interval = config.get("prune_interval_days", 90)
    last_check = meta.get("last_prune_check")

    from datetime import datetime, timezone, timedelta
    now_str = datetime.now(timezone.utc).date().isoformat()
    needs_scan = True
    if last_check:
        try:
            last_dt = datetime.fromisoformat(last_check).date()
            needs_scan = (datetime.now(timezone.utc).date() - last_dt).days >= interval
        except (ValueError, TypeError):
            pass

    if needs_scan:
        dist = distribution_summary(KG_PATH, config)
        above = dist["above_threshold"]
        # 更新检查时间
        store._kg.setdefault("meta", {})["last_prune_check"] = now_str
        store._save()

        if above > 0:
            # 检查是否已有未消耗的 prune_ready
            existing = [n for n in read_unconsumed_notifications()
                        if n.get("type") == "prune_ready"]
            if not existing:
                write_notification("prune_ready",
                    f"KG 季度检查：{above} 个节点超过老化阈值，输入 /prune 查看")
                print(f"\n  {_YELLOW}[提醒] KG 季度检查：{above} 个节点超过老化阈值，"
                      f"输入 /prune 查看{_RESET}")

    # 5. health_log 静默清理
    retention = config.get("health_log_retention_days", 90)
    removed = _cleanup_health_log(retention)
    if removed > 0:
        print(f"  {_GRAY}[清理] health_log 移除 {removed} 条超龄记录{_RESET}")


# ══════════════════════════════════════════════════════════════════
#  process_message — 对话核心（无 I/O，供 FastAPI 调用）
# ══════════════════════════════════════════════════════════════════

async def process_message(user_input: str) -> AsyncGenerator[str, None]:
    """
    处理一条用户消息，流式 yield token 字符串。
    对话历史维护在模块级 _CHAT（单用户 MVP，无需 session 管理）。
    反刍条件满足时 yield "[REFLECTION_TRIGGERED]"，调用层自行决策是否写 KG。
    """
    state = _CHAT
    if state["async_client"] is None:
        state["async_client"] = anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            base_url=os.environ.get("ANTHROPIC_BASE_URL"),
        )

    aclient       = state["async_client"]
    store         = state["store"]
    msgs          = state["messages"]
    system_prompt = state["system_prompt"]

    turn_start = len(msgs)
    msgs.append({"role": "user", "content": user_input})

    try:
        while True:
            async with aclient.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=CYBER_TOOLS,
                messages=msgs,
            ) as stream:
                async for chunk in stream.text_stream:
                    yield chunk
                final_msg = await stream.get_final_message()

            if final_msg.stop_reason == "end_turn":
                msgs.append({"role": "assistant", "content": final_msg.content})
                break

            if final_msg.stop_reason != "tool_use":
                msgs.append({"role": "assistant", "content": final_msg.content})
                break

            msgs.append({"role": "assistant", "content": final_msg.content})
            tool_results = []
            for block in final_msg.content:
                if block.type != "tool_use":
                    continue
                try:
                    result = _dispatch_tool(store, block.name, block.input)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(result, ensure_ascii=False, default=str),
                    })
                except (KeyError, ValueError) as e:
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "is_error":    True,
                        "content":     str(e),
                    })
            msgs.append({"role": "user", "content": tool_results})

    except anthropic.APIError:
        del msgs[turn_start:]
        raise

    state["turns"] += 1
    if state["turns"] % REFLECT_EVERY == 0:
        yield "[REFLECTION_TRIGGERED]"


# ══════════════════════════════════════════════════════════════════
#  REPL 主循环
# ══════════════════════════════════════════════════════════════════

def run():
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    )

    print("\n" + "═" * 56)
    print("  赛博明翰 · 认知对话终端  （输入 exit 退出）")
    print("═" * 56)

    system_prompt = build_system_prompt()
    store         = CyberBrainStore()
    print(f"[OK] 动态记忆引擎就绪，System Prompt {len(system_prompt)} 字（精简模式）")
    print("─" * 56 + "\n")

    _startup_check(store)

    # 初始化模块级聊天状态
    _CHAT["client"]        = client
    _CHAT["store"]         = store
    _CHAT["messages"]      = []
    _CHAT["turns"]         = 0
    _CHAT["system_prompt"] = system_prompt

    while True:
        # ── 接收输入 ─────────────────────────────────────────────
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[退出]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("赛博明翰: 好，拜。")
            break

        # ── /switch 专项模式切换（优先于管理员指令）────────────────
        if user_input.lower().startswith("/switch "):
            mode = user_input[8:].strip().lower()
            switched = handle_switch(mode, _CHAT["messages"])
            if switched:
                break
            continue

        # ── /review 审批队列 ─────────────────────────────────────
        if user_input.lower() == "/review":
            handle_review(store, client)
            continue

        # ── /kg 节点浏览 ─────────────────────────────────────────
        if user_input.lower().startswith("/kg"):
            sub = user_input[3:].strip().lower()
            handle_kg(store, subcommand=sub)
            continue

        # ── /prune 归档 ──────────────────────────────────────────
        if user_input.lower().startswith("/prune"):
            sub = user_input[6:].strip().lower()
            handle_prune(store, subcommand=sub)
            continue

        # ── 管理员指令拦截（/ 前缀路由至 Tool Use Agent）────────────
        if user_input.startswith("/"):
            handle_admin_command(user_input[1:].strip(), client, store)
            continue

        # ── 主聊天（调用 process_message，逐 token 打印）────────────
        print("\n赛博明翰: ", end="", flush=True)
        reflection_triggered = False

        async def _stream_turn():
            nonlocal reflection_triggered
            async for token in process_message(user_input):
                if token == "[REFLECTION_TRIGGERED]":
                    reflection_triggered = True
                else:
                    print(token, end="", flush=True)

        try:
            asyncio.run(_stream_turn())
        except anthropic.APIError as e:
            print(f"\n[API ERROR] {e}", file=sys.stderr)
            continue

        print("\n")
        print(f"  [上下文：第 {_CHAT['turns']} 轮，消息条数 {len(_CHAT['messages'])}]\n")

        # ── 反刍（CLI 模式：调用原 _reflection_cycle，保留用户确认）────
        if reflection_triggered:
            _CHAT["messages"] = _reflection_cycle(client, store, _CHAT["messages"])


# ══════════════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run()
