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

# 反馈权重默认存放位置。含用户真实发件人域名，已在 .gitignore 中排除。
DEFAULT_WEIGHTS_PATH = Path(__file__).parent / "weights.json"

# 强信号：明确要求你行动，或有实际后果 → 升到 NOW
STRONG = {
    "付款异常": r"payment\s+(unsuccessful|fail|declin)|unsuccessful|declined|"
                r"支付.{0,4}(失败|异常)|扣款失败|欠款|逾期",
    "订阅时限": r"(subscription|trial|plan).{0,20}(expire|expir|end|renew)|"
                r"will\s+expire|has\s+expired|即将到期|已过期|(?<!手)续费",
    # 「续费」必须写成 (?<!手)续费 —— 中文没有词边界，直接写会匹配到
    # 「手续费」里的子串。实测踩到：ZA Bank 的「淘宝 0 手续费优惠」
    # 因此被误判成订阅到期（BC-016）。
    "账户异常": r"unusual\s+activity|suspended|locked|账户.{0,4}(异常|冻结)|停用",
    # 面试/笔试/录用：用户 2026-09-03 明确说这类最重要。
    # 用 interview / 面试 / 笔试 / 测评 / offer 这类**进展性**词汇，
    # 刻意不用 job / 职位 / 招聘 —— 那些词命中率高但都是招聘平台的
    # 批量推荐（实测 Jobsdb 那种 noreply 推荐信就含 job/programme），
    # 混进来就变成噪音。进展性词汇天然能区分"HR 找你"和"平台群发"。
    # 英文 interview 必须搭配动作词，不能单独出现——
    # 实测踩到：McKinsey 的「An interview with...」是**访谈文章**，
    # 单独写 interview 会误判成面试通知（BC-016）。
    # 中文「面试/笔试/测评/录用」本身语义明确，无需搭配。
    "面试进展": r"interview\s+(invitation|scheduled|confirmed|reminder|request)|"
                r"(invite|inviting|schedule|arrange).{0,25}interview|"
                r"interview\s+with\s+(you|our\s+team)|"
                r"面试|笔试|online\s+assessment|测评|"
                r"offer\s+letter|录用|next\s+round|进入.{0,4}(面试|下一轮)|"
                r"邀请.{0,6}(面试|测评)",
}

# 主流个人邮箱域名。来自这些域名的邮件**大概率是真人手写**，
# 与机构群发不是一个分量（用户 2026-09-03 指出）。
PERSONAL_DOMAINS = frozenset({
    "gmail.com", "163.com", "126.com", "qq.com", "foxmail.com",
    "outlook.com", "hotmail.com", "live.com", "yahoo.com",
    "icloud.com", "me.com", "sina.com", "sohu.com", "yeah.net",
})

# 弱信号：值得知道，但不急 → DIGEST
WEAK = {
    "安全提醒": r"security|alert|安全提醒|新设备|异常登录|两步验证|2fa|password\s+changed",
    "含验证码": r"verification\s+code|confirmation\s+code|验证码|确认码|one-time|\botp\b",
    "账务变动": r"receipt|invoice|credit\s+advice|转账|存款通知|账单|扣款",
    "需要回复": r"reply\s+requested|please\s+confirm|请.{0,4}(确认|回复)|待确认",
    # 下面两条是 2026-09-03 真实验收时发现的漏报：
    # ① 4 封 GitHub「Run failed: CI - main」被判 IGNORE——自己的项目 CI 挂了
    #    却不知道，这是典型的该知道而没知道。
    "构建异常": r"run\s+failed|build\s+failed|ci.{0,12}fail|workflow.{0,10}fail|"
                r"deploy.{0,8}fail|构建失败|部署失败|测试未通过",
    # ② 2 封北邮母校邮件（毕业生邀请信、邀请参与评价）被判 IGNORE。
    #    含"邀请/评价/问卷"这类响应请求，属于有事要你做。
    "邀请问卷": r"邀请|invitation|rsvp|问卷|survey|恳请|"
                r"请.{0,6}(参加|评价|填写|参与)",
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


def _addr(field: str) -> str:
    """从 "Name <a@b.com>" 或裸 "a@b.com" 里抽出邮箱地址。"""
    m = re.search(r"<([^>]+)>|([^\s<>]+@[^\s<>]+)", field or "")
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip().lower()


def is_self_sent(mail: dict) -> bool:
    """是不是自己发给自己（测试邮件、备份、多设备同步）。

    必须排除：否则你自发的一封测试信会被当成"真人来信"，
    判定层自己给自己推通知，很荒谬。
    """
    frm, to = _addr(mail.get("from")), _addr(mail.get("to"))
    return bool(frm) and frm == to


def is_personal(mail: dict) -> bool:
    """发件人是否来自个人邮箱域名，且不是自己发的。"""
    if is_self_sent(mail):
        return False
    dom = re.search(r"@([\w.\-]+)", _addr(mail.get("from")))
    return bool(dom) and dom.group(1) in PERSONAL_DOMAINS


def signals(mail: dict) -> list[str]:
    """识别一封邮件命中的所有信号。"""
    text = f"{mail.get('subject', '')} {mail.get('body', '')}".lower()
    out = _matches(STRONG, text) + _matches(WEAK, text) + _matches(NOISE, text)
    if is_personal(mail):
        out.append("个人来信")
    return out


def classify(mail: dict, weights: dict[str, int] | None = None) -> str:
    """判定一封邮件属于哪一档。

    weights: 反馈权重（域名 -> 调整值，负=用户觉得不重要）。
    只能让档位**下降一档**，不能上升——宁可漏不要吵。
    """
    subject = (mail.get("subject") or "")
    text = f"{subject} {mail.get('body', '')}".lower()

    # 强信号**只扫主题**。原因（BC-016）：营销邮件正文动辄几千字，
    # 什么词都可能出现，扫全文必然误触发。升级到「要紧」需要主题明确表态，
    # 主题的措辞也是发件人最想让你看到的部分，用它判断最准。
    # 弱信号仍扫全文——它只是进汇总，宁可宽一些。
    strong = _matches(STRONG, subject.lower())
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
        # 无任何信号：个人来信进汇总，机构群发沉底。
        # 不能一律进汇总——否则半天汇总会被无信号的机构邮件塞满，
        # 真要看的东西反而被淹掉。
        level = DIGEST if is_personal(mail) else IGNORE

    # 个人来信**保底进汇总**：真人手写的东西不该被沉到 IGNORE。
    # 注意 is_personal 已排除自发，否则自己的测试信会触发这条。
    if level == IGNORE and is_personal(mail):
        level = DIGEST

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
