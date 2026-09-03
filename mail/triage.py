"""
mail/triage.py — 邮件重要性判定

为什么需要它：邮件能收了，但 40 封平铺在面前跟收件箱没区别。
判定层负责分成三档，只对真正要紧的打断你。

核心原则：**宁可漏，不要吵**
误报的后果是你会关掉通知，系统随即失效——这是唯一一个"做错了就彻底没用"
的失败模式。漏报顶多晚半天看到，可恢复。所以拿不准就进汇总，不打断。

三层判定：
    规则层  通用信号（本期实现）
    记忆层  个性化：涉及你在跟的项目吗（**本期只留接口**）
    反馈层  校准：你标"不重要"就降权（本期实现）

记忆层为什么本期留空：它依赖记忆治理（BC-011 来源 / BC-012 去重 /
BC-005 supersede），那些还没做。现在硬接等于在不可靠数据上做判定，
会得出"涉及你在跟的项目"这种看似聪明实则随机的结论。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

NOW, DIGEST, IGNORE = "NOW", "DIGEST", "IGNORE"

# 强信号：明确要求你行动，或有实际后果 → 升到 NOW
STRONG = {
    "付款异常": r"payment\s+(unsuccessful|fail|declin)|unsuccessful|declined|"
                r"支付.{0,4}(失败|异常)|扣款失败|欠款|逾期",
    "订阅时限": r"(subscription|trial|plan).{0,20}(expire|expir|end|renew)|"
                r"will\s+expire|has\s+expired|即将到期|已过期|续费",
    "账户异常": r"unusual\s+activity|suspended|locked|账户.{0,4}(异常|冻结)|停用",
}

# 弱信号：值得知道，但不急 → DIGEST
WEAK = {
    "安全提醒": r"security|alert|安全提醒|新设备|异常登录|两步验证|2fa|password\s+changed",
    "含验证码": r"verification\s+code|confirmation\s+code|验证码|确认码|one-time|\botp\b",
    "账务变动": r"receipt|invoice|credit\s+advice|转账|存款通知|账单|扣款",
    "需要回复": r"reply\s+requested|please\s+confirm|请.{0,4}(确认|回复)|待确认",
}

# 降权信号：明确不需要你行动 → IGNORE
NOISE = {
    "营销推广": r"unsubscribe|退订|promo|sale\s+ends|限时优惠|打折",
    "纯通知": r"do\s+not\s+reply|no-reply|noreply",
}


def _matches(patterns: dict[str, str], text: str) -> list[str]:
    return [name for name, pat in patterns.items()
            if re.search(pat, text, re.IGNORECASE)]


def _domain(mail: dict) -> str:
    """取发件人域名，作为反馈权重的作用粒度。

    用域名而不是完整地址：同一个服务从不同子地址发信应被同等对待，
    而整封邮件做粒度又太细（每封都是新样本，学不到东西）。
    """
    frm = (mail.get("from") or "").lower()
    m = re.search(r"@([\w.\-]+)", frm)
    return m.group(1) if m else (frm or "unknown")


def signals(mail: dict) -> list[str]:
    """识别一封邮件命中的所有信号。"""
    text = f"{mail.get('subject', '')} {mail.get('body', '')}".lower()
    return (_matches(STRONG, text) + _matches(WEAK, text)
            + _matches(NOISE, text))


def classify(mail: dict, weights: dict[str, int] | None = None) -> str:
    """判定一封邮件属于哪一档。

    weights: 反馈权重（域名 -> 调整值，负=用户觉得不重要）。
    只能让档位**下降一档**，不能上升——宁可漏不要吵。
    """
    text = f"{mail.get('subject', '')} {mail.get('body', '')}".lower()
    strong = _matches(STRONG, text)
    weak = _matches(WEAK, text)
    noise = _matches(NOISE, text)

    # 定级：强信号优先，其次弱信号，纯噪声沉底
    if strong:
        level = NOW
    elif weak:
        level = DIGEST
    elif noise:
        level = IGNORE
    else:
        # 无任何信号：真人来信默认进汇总，群发默认忽略
        level = IGNORE if noise or "no-reply" in (mail.get("from") or "").lower() else DIGEST

    # 反馈权重：只降不升
    adj = (weights or {}).get(_domain(mail), 0)
    if adj < 0 and level == NOW:
        level = DIGEST
    elif adj < 0 and level == DIGEST:
        level = IGNORE
    return level


# ── 反馈层 ──────────────────────────────────────────────────

def load_weights(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def record_feedback(mail: dict, path: Path, delta: int = -1) -> dict[str, int]:
    """记录一次反馈（默认"不重要" → 该域名权重 -1）。

    只影响排序，不做硬过滤——误标一次不至于让邮件永远消失。
    """
    weights = load_weights(path)
    dom = _domain(mail)
    weights[dom] = max(-3, min(3, weights.get(dom, 0) + delta))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(weights, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return weights


def triage(
    mails: list[dict],
    weights: dict[str, int] | None = None,
    dedupe: bool = True,
) -> dict[str, list[dict]]:
    """批量分档，返回 {NOW: [...], DIGEST: [...], IGNORE: [...]}。

    dedupe —— **默认值不能关**，理由是真实验收时踩到的：
    10 封 OnlyFans「订阅过期」被当成 10 件独立要事，全部进 NOW。
    每小时推一次就是 10 条一模一样的通知——用户第一反应必然是关掉它，
    系统随即失效。重复不是"信息多"，是噪音放大器。

    规则：同一发件人域名 + 同一组信号，只保留**最新**一封在原档，
    其余降级到 DIGEST（仍然看得到，但不打扰）。
    """
    out: dict[str, list[dict]] = {NOW: [], DIGEST: [], IGNORE: []}
    for m in mails:
        level = classify(m, weights)
        item = dict(m)
        item["level"] = level
        item["signals"] = signals(m)
        out[level].append(item)

    if dedupe:
        seen: set[tuple[str, tuple[str, ...]]] = set()
        demoted: list[dict] = []
        for item in out[NOW]:
            key = (_domain(item), tuple(sorted(item["signals"])))
            if key in seen:
                item["level"] = DIGEST
                item["deduped"] = True
                demoted.append(item)
            else:
                seen.add(key)
        if demoted:
            out[NOW] = [i for i in out[NOW] if i["level"] == NOW]
            out[DIGEST] = demoted + out[DIGEST]
    return out
