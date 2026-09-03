"""
mail/schedule.py — 定时检查与分级汇报

节奏（用户 2026-09-02 定的）：
    每小时  静默 check：拉取新邮件 → 判定 → 分流
    NOW 档  立即输出（等推送通道就位后改为推送）
    半天    把攒下的 DIGEST 汇总输出一次

**幂等是硬要求**：同一封邮件只能汇报一次。
重复汇报的后果和判定误报一样——你会关掉它，系统随即失效。

**推送通道缺失时的降级**：目前没有 Web Push / 服务器，
所以输出落到文件（mail/outbox.log）。等通道就位，
只要替换 `_emit()` 一个函数即可，其余逻辑不动。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from mail.adapter import fetch_recent
from mail.triage import DIGEST, NOW, load_weights, triage

STATE_PATH = Path(__file__).parent / "state.json"
OUTBOX_PATH = Path(__file__).parent / "outbox.log"
DEFAULT_WEIGHTS = Path(__file__).parent / "weights.json"

HALF_DAY_SECONDS = 12 * 3600


def _mail_key(provider: str, mail: dict) -> str:
    """邮件唯一标识。**必须带 provider**——两个邮箱可能有相同内部 id。"""
    return f"{provider}:{mail.get('id', '')}"


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"reported": [], "last_check": None, "last_digest": None,
                "digest_buffer": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"reported": [], "last_check": None, "last_digest": None,
                "digest_buffer": []}
    data.setdefault("reported", [])
    data.setdefault("digest_buffer", [])
    return data


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _emit(text: str, path: Path = OUTBOX_PATH) -> None:
    """输出一条汇报。**推送通道就位后只需改这个函数**。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {text}\n")


def check_once(
    providers=("gmail", "netease"),
    limit: int = 25,
    state_path: Path = STATE_PATH,
    weights_path: Path = DEFAULT_WEIGHTS,
    now: float | None = None,
) -> dict:
    """执行一次检查。返回本次的汇报摘要。

    now: 注入时间戳，便于测试半天节奏而不必真等 12 小时。
    """
    now = time.time() if now is None else now
    state = load_state(state_path)
    reported = set(state.get("reported", []))
    weights = load_weights(weights_path)

    fresh = []
    for p in providers:
        try:
            mails = fetch_recent(p, limit=limit)
        except Exception as exc:
            _emit(f"[{p}] 拉取失败：{type(exc).__name__}")
            continue
        for m in mails:
            key = _mail_key(p, m)
            if key in reported:
                continue
            m["_provider"] = p
            m["_key"] = key
            fresh.append(m)

    out = triage(fresh, weights=weights) if fresh else {NOW: [], DIGEST: []}

    # NOW：立即输出
    urgent = []
    for m in out.get(NOW, []):
        line = f"要紧 · {m['subject'][:50]}（{m['from'][:34]}）"
        _emit(line)
        urgent.append(line)

    # DIGEST：攒着
    buffer = list(state.get("digest_buffer", []))
    for m in out.get(DIGEST, []):
        buffer.append({"key": m["_key"],
                       "subject": m.get("subject", ""),
                       "from": m.get("from", ""),
                       "at": datetime.fromtimestamp(now).isoformat()})

    # 新汇报过的都记下来，保证幂等
    state["reported"] = sorted(reported | {m["_key"] for m in fresh})
    state["digest_buffer"] = buffer
    state["last_check"] = datetime.fromtimestamp(now).isoformat()

    # 半天到了就汇总
    digested = []
    last = state.get("last_digest")
    due = False
    if last:
        try:
            due = (now - datetime.fromisoformat(last).timestamp()
                   >= HALF_DAY_SECONDS)
        except (ValueError, TypeError):
            due = True
    else:
        due = bool(buffer)           # 首次：有内容就发一次

    if due and buffer:
        _emit(f"汇总 · 半天内有 {len(buffer)} 封值得一看")
        for item in buffer[:20]:
            _emit(f"    · {item['subject'][:48]}（{item['from'][:32]}）")
            digested.append(item["subject"])
        state["last_digest"] = datetime.fromtimestamp(now).isoformat()
        state["digest_buffer"] = []

    save_state(state, state_path)
    return {"fresh": len(fresh), "urgent": urgent,
            "digested": digested, "buffered": len(state["digest_buffer"])}


def run_daemon(interval_minutes: int = 60, **kw) -> None:
    """常驻循环。部署到服务器后由 systemd 或 nohup 拉起。

    没有做指数退避之外的花活：失败就等下一轮，
    因为邮件检查晚一小时问题不大，复杂重试反而容易堆积。
    """
    while True:
        try:
            check_once(**kw)
        except Exception:
            pass                      # 下一轮再来，不因单次失败退出
        time.sleep(interval_minutes * 60)
