"""
build_kg.py
赛博明翰认知知识图谱构建流水线
将 Yuanbao_Battle_Raw.md 批次处理为 yuanbao_cyber_minghan_kg.json

用法:
    python build_kg.py --batch 0      # 只跑 Batch 0
    python build_kg.py --all          # 跑全部批次
    python build_kg.py --list         # 列出所有批次定义
"""

# ── 标准库 ────────────────────────────────────────────────────────
import argparse
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 第三方库 ──────────────────────────────────────────────────────
import anthropic  # pip install anthropic

# ══════════════════════════════════════════════════════════════════
#  全局配置
# ══════════════════════════════════════════════════════════════════

MD_PATH  = Path(__file__).parent.parent / "archive_sources" / "Yuanbao_Battle_Raw.md"
KG_PATH  = Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"

MODEL    = os.environ.get("MODEL", "deepseek-v4-pro")          # 分析用模型
MAX_TOKENS = 4096                       # 每次 API 调用最大 token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("kg_builder")

# ── 批次定义：(batch_id, round_start, round_end, 主题描述) ─────────
# round 编号为 MD 内的 "第 N 轮"，对话 2 单独用 conv_id 区分
BATCH_DEFS: List[Tuple[str, int, int, str]] = [
    ("Batch0",   1,  16, "Soul社交策略探讨：被动匹配、30秒法则、拒绝发动态"),
    ("Batch1",  17,  35, "哲学自辩+性格初显：意义解构、愿者上钩、INFP画像修正"),
    ("Batch2",  36,  55, "人生路径回溯：清华附中→北邮→港大，速通模式萌芽"),
    ("Batch3",  56,  76, "蓝标实习+Vibe Coding：数据飞轮、工程洁癖、爱答不理"),
    ("Batch4",  77, 100, "职业迷茫+压哨绝杀：悬崖成瘾、蒸馏自我启动"),
    ("Batch5", 101, 135, "弓佳彤情感核心：初中记忆、不可知变量、替代失败"),
    ("Batch6", 136, 382, "延毕危机+量化认知画像：系统升级分析、协议协商"),
    ("Batch7",   1,   6, "对话2·认知协议协商：中间态协议、理性基底"),
]


# ══════════════════════════════════════════════════════════════════
#  数据结构
# ══════════════════════════════════════════════════════════════════

@dataclass
class Turn:
    round_num: int
    timestamp: str
    speaker:   str        # "Cyber_Minghan" | "Yuanbao"
    text:      str
    conv_id:   str = ""   # "conv1" | "conv2"
    batch_id:  str = ""


@dataclass
class DynamicItem:
    layer:       str      # "Id" | "Ego" | "Superego"
    event_label: str
    description: str
    evidence:    str      # 原文摘录
    batch_id:    str
    round_refs:  List[int] = field(default_factory=list)


@dataclass
class Interaction:
    event:      str
    trigger:    str
    resolution: str
    batch_id:   str
    timestamp:  str = ""
    round_refs: List[int] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
#  模块 1 — Parser（已完整实现）
# ══════════════════════════════════════════════════════════════════

class Parser:
    """
    负责将 Yuanbao_Battle_Raw.md 解析为结构化 Turn 列表，
    并按 BATCH_DEFS 的语义边界切分为批次字典。
    """

    # 匹配章节头：### [2026-05-25 18:26:46 UTC] 第 1 轮
    _TURN_HEADER = re.compile(
        r"^### \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)\] 第 (\d+) 轮",
        re.MULTILINE,
    )
    # 匹配会话头：## 对话 1：...
    _CONV_HEADER = re.compile(r"^## 对话\s*(\d+)[：:]", re.MULTILINE)
    # 匹配发言人标记
    _SPEAKER = re.compile(r"\*\*\[(Cyber_Minghan|Yuanbao)\]\*\*")

    # 纯格式噪声过滤
    _NOISE_LINE = re.compile(
        r"^已暂停生成\.?$|"
        r"^\[\]\(@[^\)]+\)$|"
        r"^\[citation:\d+\]$|"
        r"^-{3,}$",
        re.MULTILINE,
    )

    def load_and_split_turns(self, md_path: Path) -> List[Turn]:
        """
        读取 MD 文件，按 '### [时间戳] 第 N 轮' 切分为 Turn 列表。

        算法：
        1. 先按会话头切出各会话的文本段落
        2. 在每个段落内，用轮次头定位每条 Turn 的起止位置
        3. 提取 speaker 和正文，清洗 Markdown 格式噪声
        """
        raw = md_path.read_text(encoding="utf-8")

        # ── Step 1: 切分会话段落 ──────────────────────────────────
        conv_matches = list(self._CONV_HEADER.finditer(raw))
        segments: List[Tuple[str, str]] = []

        if conv_matches:
            for i, cm in enumerate(conv_matches):
                conv_id = f"conv{cm.group(1)}"
                seg_start = cm.start()
                seg_end   = conv_matches[i + 1].start() if i + 1 < len(conv_matches) else len(raw)
                segments.append((conv_id, raw[seg_start:seg_end]))
        else:
            segments = [("conv1", raw)]

        turns: List[Turn] = []

        # ── Step 2: 在每段内切分 Turn ─────────────────────────────
        for conv_id, seg in segments:
            turn_matches = list(self._TURN_HEADER.finditer(seg))

            for i, tm in enumerate(turn_matches):
                ts        = tm.group(1)
                round_num = int(tm.group(2))

                # Turn 正文从 header 末尾到下一个 header 开头
                body_start = tm.end()
                body_end   = turn_matches[i + 1].start() if i + 1 < len(turn_matches) else len(seg)
                body       = seg[body_start:body_end]

                # ── Step 3: 提取 speaker ──────────────────────────
                sm = self._SPEAKER.search(body)
                if not sm:
                    logger.debug("conv=%s 轮次=%d 未找到 speaker，跳过", conv_id, round_num)
                    continue
                speaker = sm.group(1)

                # ── Step 4: 提取并清洗正文 ────────────────────────
                text = self._clean(body[sm.end():])
                if not text:
                    continue

                turns.append(Turn(
                    round_num=round_num,
                    timestamp=ts,
                    speaker=speaker,
                    text=text,
                    conv_id=conv_id,
                ))

        logger.info("[Parser] 解析完成：%d 条 Turn，%d 个会话", len(turns), len(segments))
        return turns

    def batch_turns(
        self,
        turns: List[Turn],
        batch_defs: List[Tuple[str, int, int, str]] = BATCH_DEFS,
    ) -> Dict[str, List[Turn]]:
        """
        按 BATCH_DEFS 的语义边界将 Turn 分配到各批次。

        规则：
        - Batch7 对应 conv2，其余批次对应 conv1
        - round_num 落在 [start, end] 闭区间的 Turn 进入该批次
        - 同一条 Turn 只属于一个批次（边界不重叠）
        """
        batches: Dict[str, List[Turn]] = {}

        for batch_id, r_start, r_end, desc in batch_defs:
            target_conv = "conv2" if batch_id == "Batch7" else "conv1"

            matched = [
                t for t in turns
                if t.conv_id == target_conv and r_start <= t.round_num <= r_end
            ]
            for t in matched:
                t.batch_id = batch_id  # 回填 batch_id

            batches[batch_id] = matched
            logger.info(
                "[Parser] %-8s → %3d 条 Turn  轮次[%d-%d]  %s",
                batch_id, len(matched), r_start, r_end, desc,
            )

        return batches

    def get_batch(
        self,
        batch_id: str,
        turns: Optional[List[Turn]] = None,
        md_path: Path = MD_PATH,
    ) -> List[Turn]:
        """便捷方法：直接返回指定 batch_id 的 Turn 列表。"""
        if turns is None:
            turns = self.load_and_split_turns(md_path)
        batches = self.batch_turns(turns)
        return batches.get(batch_id, [])

    # ── 内部工具 ──────────────────────────────────────────────────

    def _clean(self, text: str) -> str:
        """剥离 Markdown 格式符号，保留语义文本。"""
        # 去掉噪声行
        text = self._NOISE_LINE.sub("", text)
        # 去掉 blockquote 前缀（> ）
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
        # 去掉加粗/斜体符号，保留内容
        text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
        # 去掉行内代码符号，保留内容
        text = re.sub(r"`([^`\n]+)`", r"\1", text)
        # 去掉 citation 标记
        text = re.sub(r"\[citation:\d+\]", "", text)
        # 折叠多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


# ══════════════════════════════════════════════════════════════════
#  模块 2 — SignalDetector
# ══════════════════════════════════════════════════════════════════

class SignalDetector:
    """基于关键词规则，从用户文本中检测 Id/Superego/Ego 信号。"""

    # Id：原始冲动、欲望、本能驱动
    # Id：原始冲动、欲望、本能驱动、失控感
    _ID_KEYWORDS = [
        "想要", "渴望", "爽", "上瘾", "冲动", "本能", "欲望", "刺激",
        "悬崖", "压哨", "懒", "懒得", "拖", "爽感", "快感", "不想", "逃",
        "好玩", "有趣", "爱", "喜欢", "不爽", "烦",
        "控制不住", "忍不住", "停不下来", "就是想", "偏要", "任性",
    ]
    # Superego：内化规范、道德压力、自我批判、应然焦虑
    _SUPEREGO_KEYWORDS = [
        "应该", "本该", "必须", "不能", "规则", "规范", "道德", "原则",
        "责任", "愧疚", "羞耻", "失败", "对不起", "要求", "标准", "自律",
        "不对", "错了", "没做到", "要求自己", "纪律", "理性",
        "理应", "本应", "早该", "欠", "亏", "对不起自己",
    ]
    # Ego：现实协商、策略权衡、防御机制、妥协方案
    _EGO_KEYWORDS = [
        "但是", "所以", "因此", "权衡", "策略", "方案", "折中", "平衡",
        "现实", "可行", "计划", "安排", "处理", "协商", "妥协", "调整",
        "试试", "看看", "先", "然后", "步骤", "分析", "判断",
        "合理化", "反正", "也还好", "还行", "将就", "凑合",
    ]

    _LAYER_MAP = {
        "Id":       _ID_KEYWORDS,
        "Superego": _SUPEREGO_KEYWORDS,
        "Ego":      _EGO_KEYWORDS,
    }

    def extract_user_turns(self, batch: List[Turn]) -> List[Turn]:
        """过滤出批次中属于 Cyber_Minghan 的发言。"""
        return [t for t in batch if t.speaker == "Cyber_Minghan"]

    def detect_event_signals(self, user_text: str) -> List[dict]:
        """
        对单条用户文本做关键词扫描，返回命中的信号列表。
        每条信号：{layer, keyword, context}
        context 为关键词前后 20 字的窗口。
        """
        signals: List[dict] = []
        for layer, keywords in self._LAYER_MAP.items():
            for kw in keywords:
                idx = user_text.find(kw)
                while idx != -1:
                    start = max(0, idx - 20)
                    end   = min(len(user_text), idx + len(kw) + 20)
                    signals.append({
                        "layer":   layer,
                        "keyword": kw,
                        "context": user_text[start:end].replace("\n", " "),
                    })
                    idx = user_text.find(kw, idx + 1)
        return signals

    def classify_dynamic_layer(self, signals: List[dict]) -> str:
        """
        根据信号频率投票，返回主导层：'Id' | 'Superego' | 'Ego'。
        无信号时默认返回 'Ego'。
        """
        if not signals:
            return "Ego"
        counts: Dict[str, int] = {"Id": 0, "Superego": 0, "Ego": 0}
        for s in signals:
            counts[s["layer"]] += 1
        return max(counts, key=lambda k: counts[k])


# ══════════════════════════════════════════════════════════════════
#  模块 3 — FreudianEngine
# ══════════════════════════════════════════════════════════════════

_FREUDIAN_SYSTEM = """\
你是一位专业心理动力学分析师，专注弗洛伊德三层结构（Id / Ego / Superego）。
分析对象：赛博明翰（Cyber_Minghan），北邮 AI + 港大 CS 背景，INFP 倾向，典型速通型人格。

输出规则：
1. 只输出 JSON 数组，不附任何解释文字
2. 每个元素格式：
   {"event_label": "...", "description": "...", "evidence": "原文摘录(≤60字)"}
3. 每个批次至多 5 条，选最显著的动力学事件
4. description 使用专业心理动力学术语，≤80 字
5. evidence 必须是对话原文的直接引用
6. 【重要】JSON 字符串内部禁止使用中文弯引号 " " ，如需引用请用直角引号「」或不加引号
"""

_ID_USER_TMPL = """\
以下是批次 {batch_id} 中 Cyber_Minghan 的发言片段：

{text}

任务：识别其中的 Id 层动力学事件（原始冲动、本能欲望、快感驱动、逃避冲动）。
输出 JSON 数组。
"""

_SUPEREGO_USER_TMPL = """\
以下是批次 {batch_id} 中 Cyber_Minghan 的发言片段：

{text}

任务：识别其中的 Superego 层动力学事件（内化规范、道德压力、自我批判、应然焦虑）。
输出 JSON 数组。
"""

_EGO_USER_TMPL = """\
以下是批次 {batch_id} 中 Cyber_Minghan 的发言片段：

{text}

任务：识别其中的 Ego 层动力学事件（现实协商、策略权衡、防御机制、妥协方案）。
输出 JSON 数组。
"""


class FreudianEngine:
    """
    调用 Claude API 对每个批次的用户发言进行弗洛伊德动力学分析，
    输出 Id/Ego/Superego 三个动力学层的 DynamicItem 列表。
    """

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    # ── 内部：构建发言摘要文本 ─────────────────────────────────────

    def _build_user_text(self, batch: List[Turn], max_chars: int = 6000) -> str:
        """将批次内用户发言拼接为带轮次标注的文本，截断到 max_chars。"""
        parts = []
        for t in batch:
            if t.speaker != "Cyber_Minghan":
                continue
            parts.append(f"[第{t.round_num}轮] {t.text[:400]}")
        combined = "\n\n".join(parts)
        return combined[:max_chars]

    # ── 内部：调用 API 并解析 JSON ────────────────────────────────

    @staticmethod
    def _sanitize_json(raw: str) -> str:
        # Curly/smart quotes inside JSON string values must become single quotes,
        # NOT straight doubles -- otherwise they break the JSON structure.
        return (
            raw
            .replace("\u201c", "'").replace("\u201d", "'")
            .replace("\u2018", "'").replace("\u2019", "'")
            .replace("\u3001", ",")
            .replace("\u2026", "...")
            .replace("\uff0c", ",")
            .replace("\uff1a", ":")
        )

    def _call_and_parse(
        self, batch_id: str, user_prompt: str, layer: str
    ) -> List[DynamicItem]:
        """发送请求，解析返回的 JSON 数组为 DynamicItem 列表。"""
        try:
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=_FREUDIAN_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = resp.content[0].text.strip()
            # 提取 JSON 数组（防止模型多输出文字）
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if not m:
                logger.warning("[FreudianEngine] %s %s：未找到 JSON 数组", batch_id, layer)
                return []
            items = json.loads(self._sanitize_json(m.group()))
        except Exception as e:
            logger.error("[FreudianEngine] %s %s API 调用失败: %s", batch_id, layer, e)
            return []

        results: List[DynamicItem] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append(DynamicItem(
                layer=layer,
                event_label=item.get("event_label", "未命名事件"),
                description=item.get("description", ""),
                evidence=item.get("evidence", ""),
                batch_id=batch_id,
                round_refs=[],
            ))
        logger.info("[FreudianEngine] %s %s → %d 条", batch_id, layer, len(results))
        return results

    # ── 公开接口 ──────────────────────────────────────────────────

    def analyze_id_dynamics(self, batch: List[Turn]) -> List[DynamicItem]:
        batch_id  = batch[0].batch_id if batch else "unknown"
        user_text = self._build_user_text(batch)
        if not user_text:
            return []
        prompt = _ID_USER_TMPL.format(batch_id=batch_id, text=user_text)
        return self._call_and_parse(batch_id, prompt, "Id")

    def analyze_superego_dynamics(self, batch: List[Turn]) -> List[DynamicItem]:
        batch_id  = batch[0].batch_id if batch else "unknown"
        user_text = self._build_user_text(batch)
        if not user_text:
            return []
        prompt = _SUPEREGO_USER_TMPL.format(batch_id=batch_id, text=user_text)
        return self._call_and_parse(batch_id, prompt, "Superego")

    def analyze_ego_dynamics(self, batch: List[Turn]) -> List[DynamicItem]:
        batch_id  = batch[0].batch_id if batch else "unknown"
        user_text = self._build_user_text(batch)
        if not user_text:
            return []
        prompt = _EGO_USER_TMPL.format(batch_id=batch_id, text=user_text)
        return self._call_and_parse(batch_id, prompt, "Ego")


# ══════════════════════════════════════════════════════════════════
#  模块 4 — InteractionExtractor（骨架）
# ══════════════════════════════════════════════════════════════════

_INTERACTION_SYSTEM = """\
你是一位对话动力学分析师，专注于提取人与 AI 交互中的关键心理事件三元组。
分析对象：赛博明翰（Cyber_Minghan）与元宝（Yuanbao）的对话。

输出规则：
1. 只输出 JSON 数组，不附任何解释文字
2. 每个元素格式：
   {
     "event": "事件名称(≤20字，动宾结构)",
     "trigger": "触发这一事件的直接诱因(≤60字，引用原文)",
     "resolution": "事件的结果或应对方式(≤60字，描述实际走向)"
   }
3. 每个批次至多 6 条，聚焦心理冲突、认知转折、情感爆发
4. 优先捕捉：Cyber_Minghan 主动引发的对话转向、情绪升级、策略切换
5. 【重要】JSON 字符串内部禁止使用中文弯引号 " " ，如需引用请用直角引号「」或不加引号
"""

_INTERACTION_USER_TMPL = """\
以下是批次 {batch_id} 的完整对话（含双方发言）：

{text}

任务：提取其中显著的互动事件三元组 (event, trigger, resolution)。
输出 JSON 数组。
"""


class InteractionExtractor:
    """从批次对话中提取 (event, trigger, resolution) 三元组。"""

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    # ── 内部：构建双方对话摘要文本 ────────────────────────────────

    def _build_dialogue_text(self, batch: List[Turn], max_chars: int = 7000) -> str:
        """将批次内双方发言按轮次顺序拼接，截断到 max_chars。"""
        parts = []
        for t in batch:
            tag = "用户" if t.speaker == "Cyber_Minghan" else "元宝"
            parts.append(f"[第{t.round_num}轮·{tag}] {t.text[:300]}")
        combined = "\n\n".join(parts)
        return combined[:max_chars]

    # ── 公开接口 ──────────────────────────────────────────────────

    def extract_interaction_events(self, batch: List[Turn]) -> List[Interaction]:
        """调用 API 提取三元组，返回 Interaction 列表。"""
        if not batch:
            return []
        batch_id = batch[0].batch_id
        dialogue_text = self._build_dialogue_text(batch)
        prompt = _INTERACTION_USER_TMPL.format(batch_id=batch_id, text=dialogue_text)

        try:
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=_INTERACTION_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if not m:
                logger.warning("[InteractionExtractor] %s：未找到 JSON 数组", batch_id)
                return []
            sanitized = (
                m.group()
                .replace("\u201c", "'").replace("\u201d", "'")
                .replace("\u2018", "'").replace("\u2019", "'")
                .replace("\u3001", ",").replace("\u2026", "...")
                .replace("\uff0c", ",").replace("\uff1a", ":")
            )
            items = json.loads(sanitized)
        except Exception as e:
            logger.error("[InteractionExtractor] %s API 调用失败: %s", batch_id, e)
            return []

        results: List[Interaction] = []
        # 取首尾轮次的时间戳作为事件时间
        ts = batch[0].timestamp if batch else ""
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append(Interaction(
                event=item.get("event", "未命名事件"),
                trigger=item.get("trigger", ""),
                resolution=item.get("resolution", ""),
                batch_id=batch_id,
                timestamp=ts,
                round_refs=[],
            ))
        logger.info("[InteractionExtractor] %s → %d 条三元组", batch_id, len(results))
        return results

    def deduplicate_interactions(
        self, existing: List[Interaction], new: List[Interaction]
    ) -> List[Interaction]:
        """
        去重：若新条目的 event 字段与已有条目高度重叠（前8字相同），则跳过。
        返回合并后的完整列表。
        """
        existing_keys = {i.event[:8] for i in existing}
        unique_new = [i for i in new if i.event[:8] not in existing_keys]
        logger.info(
            "[InteractionExtractor] 去重：新增 %d 条，过滤 %d 条重复",
            len(unique_new), len(new) - len(unique_new),
        )
        return existing + unique_new

    def enrich_interaction_context(
        self, interaction: Interaction, full_turns: List[Turn]
    ) -> Interaction:
        """
        从 full_turns 中找到与 trigger 文本最接近的轮次，
        回填 round_refs 字段。
        """
        if not interaction.trigger:
            return interaction
        kw = interaction.trigger[:15]  # 取前15字作为查找锚点
        refs = [
            t.round_num for t in full_turns
            if kw in t.text and t.conv_id == (
                "conv2" if interaction.batch_id == "Batch7" else "conv1"
            )
        ]
        interaction.round_refs = sorted(set(refs))[:5]  # 最多记5个
        return interaction


# ══════════════════════════════════════════════════════════════════
#  模块 5 — KGBuilder
# ══════════════════════════════════════════════════════════════════

_KG_TEMPLATE: dict = {
    "schema_version": "1.0",
    "created_at": "",
    "updated_at": "",
    "processed_batches": [],
    "nodes": {
        "Cyber_Minghan": {
            "Id_Dynamics":       [],
            "Superego_Dynamics": [],
            "Ego_Dynamics":      [],
        }
    },
    "interactions": [],
    "metadata": {},
}


class KGBuilder:
    """负责图谱的初始化、增量合并与持久化落盘。"""

    def init_or_load_kg(self, output_path: Path) -> dict:
        """
        断点续读：若 output_path 已存在且合法则加载，否则返回空模板。
        """
        if output_path.exists():
            try:
                kg = json.loads(output_path.read_text(encoding="utf-8"))
                processed = kg.get("processed_batches", [])
                logger.info(
                    "[KGBuilder] 加载已有图谱：%d 条动力学事件，%d 条互动，"
                    "已处理批次：%s",
                    self._count_dynamics(kg),
                    len(kg.get("interactions", [])),
                    processed,
                )
                return kg
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("[KGBuilder] 已有文件损坏 (%s)，重新初始化", e)

        now = datetime.now(timezone.utc).isoformat()
        kg = json.loads(json.dumps(_KG_TEMPLATE))  # 深拷贝模板
        kg["created_at"] = now
        kg["updated_at"] = now
        logger.info("[KGBuilder] 初始化空图谱")
        return kg

    def merge_batch_into_kg(self, kg: dict, batch_result: dict) -> dict:
        """
        将单批次分析结果增量合并进图谱。
        batch_result 结构：
        {
          "batch_id": str,
          "dynamics": [DynamicItem asdict, ...],
          "interactions": [Interaction asdict, ...],
        }
        """
        batch_id = batch_result.get("batch_id", "unknown")

        # 防重复处理
        if batch_id in kg.get("processed_batches", []):
            logger.info("[KGBuilder] %s 已处理，跳过合并", batch_id)
            return kg

        node = kg["nodes"]["Cyber_Minghan"]

        for item in batch_result.get("dynamics", []):
            layer = item.get("layer", "Ego")
            key = f"{layer}_Dynamics"
            if key not in node:
                node[key] = []
            node[key].append(item)

        kg["interactions"].extend(batch_result.get("interactions", []))
        kg["processed_batches"].append(batch_id)
        kg["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "[KGBuilder] 合并 %s：动力学 +%d，互动 +%d",
            batch_id,
            len(batch_result.get("dynamics", [])),
            len(batch_result.get("interactions", [])),
        )
        return kg

    def save_kg(self, kg: dict, output_path: Path) -> None:
        """原子写入：先写临时文件，再重命名，防止写到一半时崩溃损坏文件。"""
        tmp_path = output_path.with_suffix(".tmp.json")
        try:
            tmp_path.write_text(
                json.dumps(kg, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(output_path)
            logger.info("[KGBuilder] 已落盘：%s", output_path)
        except Exception as e:
            logger.error("[KGBuilder] 写入失败: %s", e)
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def generate_metadata(self, kg: dict, total_batches: int) -> dict:
        """生成图谱统计元数据，写入 kg['metadata'] 并返回。"""
        node = kg["nodes"]["Cyber_Minghan"]
        meta = {
            "total_batches_defined": total_batches,
            "processed_batches":     len(kg.get("processed_batches", [])),
            "id_dynamics_count":     len(node.get("Id_Dynamics", [])),
            "ego_dynamics_count":    len(node.get("Ego_Dynamics", [])),
            "superego_dynamics_count": len(node.get("Superego_Dynamics", [])),
            "interactions_count":    len(kg.get("interactions", [])),
            "generated_at":          datetime.now(timezone.utc).isoformat(),
        }
        kg["metadata"] = meta
        return meta

    # ── 内部工具 ──────────────────────────────────────────────────

    @staticmethod
    def _count_dynamics(kg: dict) -> int:
        node = kg.get("nodes", {}).get("Cyber_Minghan", {})
        return (
            len(node.get("Id_Dynamics", []))
            + len(node.get("Ego_Dynamics", []))
            + len(node.get("Superego_Dynamics", []))
        )


# ══════════════════════════════════════════════════════════════════
#  模块 6 — Orchestrator
# ══════════════════════════════════════════════════════════════════

class Orchestrator:
    """主流水线调度器，协调所有模块完成端到端处理。"""

    def __init__(self):
        client             = anthropic.Anthropic()   # 读取 ANTHROPIC_API_KEY
        self.parser        = Parser()
        self.detector      = SignalDetector()
        self.freudian      = FreudianEngine(client)
        self.extractor     = InteractionExtractor(client)
        self.kg_builder    = KGBuilder()

    # ── 单批次处理 ────────────────────────────────────────────────

    def process_single_batch(
        self,
        batch_id: str,
        batch: List[Turn],
        kg: dict,
        output_path: Path,
    ) -> dict:
        """
        对一个批次执行完整分析，将结果合并进 kg 并落盘。
        返回本批次的 batch_result 字典。
        """
        logger.info("═" * 56)
        logger.info("[Orchestrator] 开始处理 %s（%d 条 Turn）", batch_id, len(batch))

        # ── Step 1: 弗洛伊德三层动力学分析 ──────────────────────
        dynamics: List[DynamicItem] = []
        for analyze_fn, layer in [
            (self.freudian.analyze_id_dynamics,        "Id"),
            (self.freudian.analyze_superego_dynamics,  "Superego"),
            (self.freudian.analyze_ego_dynamics,       "Ego"),
        ]:
            try:
                items = analyze_fn(batch)
                dynamics.extend(items)
            except Exception as e:
                logger.error("[Orchestrator] %s %s 分析失败: %s", batch_id, layer, e)

        # ── Step 2: 互动事件三元组提取 ────────────────────────────
        interactions: List[Interaction] = []
        try:
            raw_interactions = self.extractor.extract_interaction_events(batch)
            # 去重（对比 kg 中已有记录）
            existing = [
                Interaction(**i) if isinstance(i, dict) else i
                for i in kg.get("interactions", [])
            ]
            interactions = self.extractor.deduplicate_interactions(
                existing, raw_interactions
            )
            # 只保留本批次新增部分（去重后比 existing 多出的条目）
            new_count = len(interactions) - len(existing)
            interactions = interactions[len(existing):]  # 只取增量

            # 回填 round_refs
            all_turns = batch  # 当前批次即为上下文
            interactions = [
                self.extractor.enrich_interaction_context(i, all_turns)
                for i in interactions
            ]
        except Exception as e:
            logger.error("[Orchestrator] %s 互动提取失败: %s", batch_id, e)

        # ── Step 3: 序列化 + 合并 + 落盘 ─────────────────────────
        batch_result = {
            "batch_id":     batch_id,
            "dynamics":     [asdict(d) for d in dynamics],
            "interactions": [asdict(i) for i in interactions],
        }
        kg = self.kg_builder.merge_batch_into_kg(kg, batch_result)
        self.kg_builder.generate_metadata(kg, len(BATCH_DEFS))
        self.kg_builder.save_kg(kg, output_path)

        logger.info(
            "[Orchestrator] %s 完成：动力学 %d 条，互动 %d 条",
            batch_id, len(dynamics), len(interactions),
        )
        return batch_result

    # ── 全量流水线 ────────────────────────────────────────────────

    def run_pipeline(
        self,
        md_path: Path = MD_PATH,
        output_path: Path = KG_PATH,
        target_batch: Optional[str] = None,
    ) -> None:
        """
        端到端主流程。
        - target_batch 不为 None 时只跑指定批次（支持断点续跑）
        - 否则按 BATCH_DEFS 顺序逐批处理
        """
        # 解析 MD
        turns   = self.parser.load_and_split_turns(md_path)
        batches = self.parser.batch_turns(turns)

        # 加载或初始化图谱
        kg = self.kg_builder.init_or_load_kg(output_path)

        # 确定要跑的批次列表
        if target_batch:
            batch_ids = [target_batch]
        else:
            batch_ids = [bd[0] for bd in BATCH_DEFS]

        succeeded, skipped, failed = 0, 0, 0

        for batch_id in batch_ids:
            # 断点续跑：已处理过的跳过
            if batch_id in kg.get("processed_batches", []):
                logger.info("[Orchestrator] %s 已在图谱中，跳过", batch_id)
                skipped += 1
                continue

            batch = batches.get(batch_id, [])
            if not batch:
                logger.warning("[Orchestrator] %s 无 Turn 数据，跳过", batch_id)
                skipped += 1
                continue

            try:
                self.process_single_batch(batch_id, batch, kg, output_path)
                # 重新加载 kg（save_kg 已落盘，重读确保状态一致）
                kg = self.kg_builder.init_or_load_kg(output_path)
                succeeded += 1
            except Exception as e:
                logger.error("[Orchestrator] %s 处理异常，跳过该批次: %s", batch_id, e)
                failed += 1

        logger.info(
            "═" * 56 + "\n[Orchestrator] 流水线结束：成功 %d，跳过 %d，失败 %d",
            succeeded, skipped, failed,
        )
        logger.info("[Orchestrator] 输出文件：%s", output_path)


# ══════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="KG Builder — 赛博明翰知识图谱")
    ap.add_argument("--batch",      type=str, help="执行单个批次，如 Batch0")
    ap.add_argument("--all",        action="store_true", help="执行全部批次")
    ap.add_argument("--list",       action="store_true", help="列出批次定义")
    ap.add_argument("--test-parse", action="store_true", help="仅测试解析层")
    args = ap.parse_args()

    if args.list:
        print(f"\n{'批次':<10} {'轮次范围':<12} 主题描述")
        print("─" * 70)
        for bid, rs, re_, desc in BATCH_DEFS:
            print(f"{bid:<10} 第{rs:>3}–{re_:<3}轮   {desc}")
        print()
        return

    if args.test_parse:
        parser = Parser()
        turns   = parser.load_and_split_turns(MD_PATH)
        batches = parser.batch_turns(turns)
        print(f"\n{'='*58}")
        print("  解析结果概览")
        print(f"{'='*58}")
        print(f"  总 Turn 数：{len(turns)}")
        print(f"  批次数    ：{len(batches)}")
        print()
        print(f"  {'批次':<10} {'总Turn':>6}  {'用户Turn':>8}")
        print(f"  {'─'*32}")
        for bid, bturns in batches.items():
            user_n = sum(1 for t in bturns if t.speaker == "Cyber_Minghan")
            print(f"  {bid:<10} {len(bturns):>6}  {user_n:>8}")
        print()
        return

    if args.batch:
        # 支持 "0" → "Batch0" 的简写
        batch_id = args.batch if args.batch.startswith("Batch") else f"Batch{args.batch}"
        Orchestrator().run_pipeline(target_batch=batch_id)
        return

    if args.all:
        Orchestrator().run_pipeline()
        return

    ap.print_help()


if __name__ == "__main__":
    main()
