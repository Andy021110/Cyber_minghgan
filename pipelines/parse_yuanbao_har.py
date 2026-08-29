#!/usr/bin/env python3
"""
parse_yuanbao_har.py
解析腾讯元宝 HAR 文件，输出清洗后的对话 Markdown 文档。
"""

import glob
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("yuanbao_parser")

# ── 目标 API 路径关键词 ────────────────────────────────────────────
TARGET_URL_PATTERNS = [
    "/api/user/agent/conversation/v1/detail",
    "/api/user/agent/conversation/detail",
    "/api/chat/completions",
    "/api/conversation",
]

OUTPUT_FILE = Path(__file__).parent.parent / "archive_sources" / "Yuanbao_Battle_Raw.md"


# ══════════════════════════════════════════════════════════════════
#  HAR 读取与过滤
# ══════════════════════════════════════════════════════════════════

def load_har(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_target_entry(entry: dict) -> bool:
    url = entry.get("request", {}).get("url", "")
    mime = entry.get("response", {}).get("content", {}).get("mimeType", "")
    for pattern in TARGET_URL_PATTERNS:
        if pattern in url:
            return True
    # 也捕获 event-stream 响应（SSE）
    if "event-stream" in mime:
        return True
    return False


# ══════════════════════════════════════════════════════════════════
#  SSE 流解析（备用，本 HAR 实际为纯 JSON）
# ══════════════════════════════════════════════════════════════════

def parse_sse_text(raw: str) -> str:
    """从 SSE 原始文本拼接完整内容。"""
    fragments = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in ("[DONE]", ""):
            continue
        try:
            obj = json.loads(payload)
            # OpenAI-style delta
            delta = obj.get("choices", [{}])[0].get("delta", {})
            fragments.append(delta.get("content", ""))
        except (json.JSONDecodeError, IndexError, KeyError):
            fragments.append(payload)
    return "".join(fragments)


# ══════════════════════════════════════════════════════════════════
#  元宝 JSON 响应解析
# ══════════════════════════════════════════════════════════════════

def extract_text_from_content(content_list: list) -> str:
    """从 speechesV2[].content[] 提取可读文本，保留代码块。"""
    parts = []
    for item in content_list:
        t = item.get("type", "")
        if t == "text":
            msg = item.get("msg", "").strip()
            if msg:
                parts.append(msg)
        elif t == "think":
            title = item.get("title", "深度思考").strip()
            thought = item.get("content", "").strip()
            if thought:
                parts.append(f"\n> **{title}**\n>\n> {thought.replace(chr(10), chr(10) + '> ')}\n")
        elif t == "deepSearch":
            title = item.get("title", "深度搜索").strip()
            parts.append(f"\n> **{title}**（已省略搜索详情）\n")
        elif t == "searchGuid":
            pass  # 元数据，跳过
        else:
            # 未知类型：尝试提取 msg 或 content 字段
            fallback = item.get("msg") or item.get("content") or ""
            if fallback:
                parts.append(str(fallback).strip())
    return "\n\n".join(p for p in parts if p)


def parse_convs(convs: list) -> List[dict]:
    """
    解析 convs 数组，返回标准化消息列表。
    每条消息：{id, speaker, timestamp, text}
    """
    messages = []
    for conv in convs:
        try:
            msg_id = conv.get("id", "")
            speaker = conv.get("speaker", "unknown")  # "ai" | "user"
            ts_raw = conv.get("createTime", 0)
            try:
                # createTime is Unix seconds (not ms)
                ts = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
            except Exception:
                ts = str(ts_raw)

            speeches = conv.get("speechesV2", [])
            text_parts = []
            for speech in speeches:
                content_list = speech.get("content", [])
                chunk = extract_text_from_content(content_list)
                if chunk:
                    text_parts.append(chunk)

            full_text = "\n\n".join(text_parts).strip()

            # 若 speechesV2 为空，尝试老字段 speeches
            if not full_text:
                old_speeches = conv.get("speeches", [])
                for sp in old_speeches:
                    full_text = sp.get("content", "").strip()
                    if full_text:
                        break

            if not full_text:
                logger.warning("空消息 id=%s speaker=%s，跳过", msg_id, speaker)
                continue

            messages.append(
                {"id": msg_id, "speaker": speaker, "timestamp": ts, "text": full_text}
            )
        except (KeyError, TypeError) as e:
            logger.warning("解析单条消息失败: %s，跳过", e)
    return messages


def parse_response_body(entry: dict) -> Tuple[Optional[str], List[dict]]:
    """
    解析单条 HAR entry 的响应体，返回 (conversation_title, messages)。
    """
    content = entry.get("response", {}).get("content", {})
    mime = content.get("mimeType", "")
    raw = content.get("text", "")

    if not raw:
        return None, []

    # ── 解码 base64（HAR 有时会编码二进制）──
    encoding = content.get("encoding", "")
    if encoding == "base64":
        import base64
        try:
            raw = base64.b64decode(raw).decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("base64 解码失败: %s", e)
            return None, []

    # ── SSE 流 ──
    if "event-stream" in mime:
        text = parse_sse_text(raw)
        if text:
            return None, [{"id": "", "speaker": "ai", "timestamp": "", "text": text}]
        return None, []

    # ── JSON ──
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("JSON 解析失败 (%s)，跳过该 entry", e)
        return None, []

    # 支持多层包装
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return None, []

    # 提取 title
    title = obj.get("title") or obj.get("conversationTitle") or ""

    # 提取 convs
    convs = obj.get("convs") or obj.get("messages") or obj.get("data", {}).get("convs", [])
    if not isinstance(convs, list):
        convs = []

    messages = parse_convs(convs)
    return title, messages


# ══════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════

def process_har_files(har_paths: list[str]) -> dict:
    """
    处理多个 HAR 文件，按 conversationId 合并去重，返回有序对话字典。
    结构: {conv_id: {"title": str, "messages": [...]}}
    """
    all_conversations: dict[str, dict] = {}
    seen_msg_ids: set[str] = set()

    for path in har_paths:
        logger.info("读取 HAR: %s", path)
        try:
            har = load_har(path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("无法加载 %s: %s，跳过", path, e)
            continue

        entries = har.get("log", {}).get("entries", [])
        logger.info("  共 %d 条 entries", len(entries))

        for idx, entry in enumerate(entries):
            if not is_target_entry(entry):
                continue

            url = entry.get("request", {}).get("url", "")
            started_at = entry.get("startedDateTime", "")

            # 尝试从请求体提取 conversationId
            conv_id = _extract_conv_id(entry)

            try:
                title, messages = parse_response_body(entry)
            except Exception as e:
                logger.warning("entry #%d 解析异常: %s，跳过", idx, e)
                continue

            if not messages:
                continue

            key = conv_id or f"unknown_{idx}"
            if key not in all_conversations:
                all_conversations[key] = {"title": title or key, "messages": []}
            elif title:
                all_conversations[key]["title"] = title

            # 去重：按消息 id，若无 id 则全量追加
            for msg in messages:
                mid = msg["id"]
                if mid:
                    if mid in seen_msg_ids:
                        continue
                    seen_msg_ids.add(mid)
                all_conversations[key]["messages"].append(msg)

            logger.info(
                "  [%s] +%d 条消息 (conv=%s)", started_at[:19], len(messages), key[:20]
            )

    return all_conversations


def _extract_conv_id(entry: dict) -> Optional[str]:
    """从请求体或 URL 中提取 conversationId。"""
    # 尝试 POST body
    post_data = entry.get("request", {}).get("postData", {})
    raw_body = post_data.get("text", "")
    if raw_body:
        try:
            body = json.loads(raw_body)
            cid = body.get("conversationId") or body.get("conversation_id")
            if cid:
                return str(cid)
        except json.JSONDecodeError:
            # URL-encoded 参数
            m = re.search(r"conversationId=([^&]+)", raw_body)
            if m:
                return m.group(1)

    # 尝试 URL 参数
    url = entry.get("request", {}).get("url", "")
    m = re.search(r"conversationId=([^&]+)", url)
    if m:
        return m.group(1)

    return None


def render_markdown(conversations: dict) -> str:
    """将对话字典渲染为 Markdown 字符串。"""
    lines = [
        "# Yuanbao Battle Raw — 元宝对话完整记录",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> 共 {len(conversations)} 个对话会话",
        "",
        "---",
        "",
    ]

    for conv_idx, (conv_id, conv_data) in enumerate(conversations.items(), 1):
        title = conv_data["title"] or conv_id
        messages = conv_data["messages"]

        # 按 timestamp 排序（空 timestamp 排最前）
        try:
            messages.sort(key=lambda m: m.get("timestamp") or "")
        except Exception:
            pass

        lines.append(f"## 对话 {conv_idx}：{title}")
        lines.append("")
        lines.append(f"**会话 ID：** `{conv_id}`  ")
        lines.append(f"**消息数：** {len(messages)}")
        lines.append("")

        for msg_idx, msg in enumerate(messages, 1):
            speaker = msg["speaker"]
            ts = msg["timestamp"] or "—"
            text = msg["text"]

            if speaker in ("user", "human"):
                role_tag = "**[Cyber_Minghan]**"
            else:
                role_tag = "**[Yuanbao]**"

            lines.append(f"### [{ts}] 第 {msg_idx} 轮")
            lines.append("")
            lines.append(f"{role_tag}")
            lines.append("")
            lines.append(text)
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def main():
    script_dir = Path(__file__).parent
    har_files = sorted(glob.glob(str(script_dir / "*.har")))

    if not har_files:
        logger.error("当前目录下未找到任何 .har 文件，退出。")
        sys.exit(1)

    logger.info("发现 %d 个 HAR 文件: %s", len(har_files), [Path(p).name for p in har_files])

    conversations = process_har_files(har_files)

    if not conversations:
        logger.error("未提取到任何对话数据，请检查 HAR 文件是否包含元宝 API 响应。")
        sys.exit(1)

    total_msgs = sum(len(v["messages"]) for v in conversations.values())
    logger.info("共提取 %d 个会话，%d 条消息", len(conversations), total_msgs)

    md_content = render_markdown(conversations)

    OUTPUT_FILE.write_text(md_content, encoding="utf-8")
    logger.info("已写入: %s (%d 字节)", OUTPUT_FILE, len(md_content.encode("utf-8")))

    print(f"\n✓ 完成！输出文件：{OUTPUT_FILE}")
    print(f"  对话数：{len(conversations)}，消息数：{total_msgs}")


if __name__ == "__main__":
    main()
