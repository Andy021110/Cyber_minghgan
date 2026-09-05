"""邮件重要性判定的测试。

**刻意用脱敏的合成样本，不连真实邮箱**：
- 测试要可复现（真实邮箱内容天天变，没法断言）
- 需要凭证（CI 跑不了）
- 隐私（你的邮件不该出现在代码库里）

真实邮件的验证是另一回事——见计划 Step 5，由人工核对判定结果。
"""

import pytest

from mail.triage import (
    DIGEST, IGNORE, NOW,
    _addr, _domain, classify, is_self_sent, load_weights,
    record_feedback, signals, triage,
)


def mail(subject="", body="", frm="someone@example.com"):
    return {"subject": subject, "body": body, "from": frm, "to": "me@x.com"}


# ── 强信号 → NOW（需要行动）──

def test_payment_failure_is_now():
    m = mail("Your payment was unsuccessful",
             "Stripe informed us the payment did not go through.")
    assert classify(m) == NOW
    assert "付款异常" in signals(m)


def test_subscription_expiring_is_now():
    m = mail("Your Subscription Will Expire", "Renew to keep access.")
    assert classify(m) == NOW
    assert "订阅时限" in signals(m)


def test_account_suspended_is_now():
    m = mail("Account suspended", "unusual activity detected.")
    assert classify(m) == NOW


# ── 弱信号 → DIGEST（知道就行，不急）──

def test_security_notice_is_digest_not_now():
    """安全提醒不该打断你——除非是账户异常那种强信号。"""
    m = mail("Security alert", "New sign-in from a new device.",
             frm="no-reply@accounts.example.com")
    assert classify(m) == DIGEST


def test_verification_code_is_digest():
    m = mail("Your verification code", "code: 123456")
    assert classify(m) == DIGEST


def test_receipt_is_digest():
    m = mail("Your receipt", "Thanks for your payment.")
    assert classify(m) == DIGEST


# ── 噪声 → IGNORE ──

def test_marketing_is_ignored():
    m = mail("Big sale ends tonight", "50% off everything. Unsubscribe here.")
    assert classify(m) == IGNORE


def test_pure_noreply_no_signal_is_ignored():
    m = mail("Weekly digest", "nothing actionable",
             frm="no-reply@newsletter.example.com")
    assert classify(m) == IGNORE


# ── 保守原则：拿不准不打断 ──

def test_real_person_no_signal_is_digest():
    """真人来信即使没命中任何信号，也进汇总而不是忽略。

    必须用真实个人邮箱域名——"真人"的判据是发件人域名，
    用 example.com 这类测试域名测不出这条规则。
    """
    m = mail("hi", "just saying hello", frm="friend@gmail.com")
    assert classify(m) == DIGEST


def test_unknown_content_is_never_now():
    """没有任何信号时绝不能升到 NOW——宁可漏不要吵。"""
    for subject, body in [("hello", "how are you"),
                          ("newsletter", "here is our weekly update"),
                          ("", "")]:
        assert classify(mail(subject, body)) != NOW


# ── 反馈层 ──

def test_feedback_lowers_level(tmp_path):
    m = mail("Your payment was unsuccessful", "payment did not go through")
    assert classify(m) == NOW
    w = record_feedback(m, tmp_path / "w.json", delta=-1)
    assert classify(m, w) == DIGEST, "标过不重要就该降级"


def test_feedback_never_raises_level(tmp_path):
    """反馈只能降级不能升级——避免误触把垃圾邮件推到 NOW。"""
    m = mail("Big sale", "unsubscribe here")
    assert classify(m) == IGNORE
    w = record_feedback(m, tmp_path / "w.json", delta=+1)
    assert classify(m, w) == IGNORE


def test_feedback_persists(tmp_path):
    p = tmp_path / "w.json"
    record_feedback(mail(frm="spam@example.com"), p, delta=-1)
    assert load_weights(p).get("example.com") == -1


def test_feedback_is_clamped(tmp_path):
    p = tmp_path / "w.json"
    w = {}
    for _ in range(10):
        w = record_feedback(mail(frm="x@example.com"), p, delta=-1)
    assert w["example.com"] >= -3, "权重要有下限，别让一次误标永久封杀"


def test_domain_extraction():
    assert _domain({"from": "A <b@c.example.com>"}) == "c.example.com"
    assert _domain({"from": "no-domain"}) == "no-domain"


# ── 批量 ──

def test_triage_splits_into_three_buckets():
    mails = [
        mail("Your payment was unsuccessful", "payment declined"),
        mail("Security alert", "new device"),
        mail("Sale", "unsubscribe"),
    ]
    out = triage(mails)
    assert len(out[NOW]) == 1 and len(out[DIGEST]) == 1 and len(out[IGNORE]) == 1


def test_triage_keeps_all_mails():
    mails = [mail(f"s{i}", f"b{i}") for i in range(5)]
    out = triage(mails)
    assert sum(len(v) for v in out.values()) == len(mails)


def test_triage_annotates_signals():
    out = triage([mail("Your payment was unsuccessful", "declined")])
    assert out[NOW][0]["signals"]


# ── 去重（真实验收时踩到的坑，必须守住）──

def test_duplicate_urgent_mails_collapse_to_one():
    """10 封同发件人同信号的"订阅过期"只能产生 1 条 NOW。

    真实验收的教训：Gmail+163 共 48 封里，NOW 档 12 封中有 10 封是
    OnlyFans 的重复订阅通知。每小时推一次就是 10 条一模一样的打扰。
    """
    mails = [mail("Your subscription will expire",
                  "renew now", frm="no-reply@notify.example.com")
             for _ in range(10)]
    out = triage(mails)
    assert len(out[NOW]) == 1, "重复邮件必须折叠成一条"
    assert len(out[DIGEST]) == 9, "其余降级到汇总而不是消失"


def test_dedupe_keeps_different_signals_separate():
    """同发件人但信号不同，不算重复。"""
    mails = [
        mail("payment unsuccessful", "declined", frm="billing@example.com"),
        mail("your subscription expired", "expired", frm="billing@example.com"),
    ]
    out = triage(mails)
    assert len(out[NOW]) == 2


def test_dedupe_keeps_different_senders_separate():
    mails = [
        mail("payment unsuccessful", "declined", frm="a@example.com"),
        mail("payment unsuccessful", "declined", frm="b@other.com"),
    ]
    assert len(triage(mails)[NOW]) == 2


def test_dedupe_can_be_disabled_for_inspection():
    mails = [mail("payment unsuccessful", "declined", frm="a@example.com")
             for _ in range(3)]
    assert len(triage(mails, dedupe=False)[NOW]) == 3


def test_demoted_items_are_marked():
    mails = [mail("payment unsuccessful", "declined", frm="a@example.com")
             for _ in range(2)]
    demoted = [m for m in triage(mails)[DIGEST] if m.get("deduped")]
    assert len(demoted) == 1


# ── 面试进展（用户 2026-09-03 说这类最重要）──

def test_interview_invitation_is_now():
    m = mail("Interview invitation", "We'd like to schedule an interview.",
             frm="hr@company.example.com")
    assert classify(m) == NOW
    assert "面试进展" in signals(m)


def test_written_test_is_now():
    m = mail("笔试通知", "请于本周完成在线测评", frm="recruiter@corp.example.com")
    assert classify(m) == NOW


def test_offer_letter_is_now():
    m = mail("Offer letter", "We are pleased to offer you the position.")
    assert classify(m) == NOW


def test_job_platform_blast_is_not_now():
    """招聘平台的批量职位推荐不该算——实测 Jobsdb 那种就是这种。

    它含 job / programme / recommendations，但不含 interview / 面试。
    这正是"面试进展"刻意不用 job / 职位 / 招聘 这些词的原因。
    """
    m = mail("IT Operations Graduate Programme - Hong Kong",
             "View job recommendations just for you",
             frm="noreply@e.jobsdb.example.com")
    assert classify(m) != NOW


# ── 反馈权重作用于真实域名 ──

def test_feedback_demotes_subscription_notice(tmp_path):
    """用户说 OnlyFans 订阅过期不重要 → 该域名降权后不应再进 NOW。"""
    m = mail("Your Subscription Will Expire", "renew to keep access",
             frm="no-reply@notify.onlyfans.example.com")
    assert classify(m) == NOW                      # 降权前
    w = record_feedback(m, tmp_path / "w.json", delta=-1)
    assert classify(m, w) == DIGEST                # 降权后


def test_other_subscription_still_now(tmp_path):
    """降权是**针对域名**的，不能误伤其他服务的订阅提醒。"""
    w = record_feedback({"from": "no-reply@notify.onlyfans.example.com"},
                        tmp_path / "w.json", delta=-1)
    other = mail("Your subscription will expire", "renew",
                 frm="billing@important-service.example.com")
    assert classify(other, w) == NOW


# ── 个人邮箱（用户 2026-09-03：这类应该更重要）──

def test_personal_mail_is_never_ignored():
    """真人用个人邮箱写的信，再没信号也不该沉到 IGNORE。"""
    m = mail("hi there", "long time no see", frm="friend@gmail.com")
    assert classify(m) != IGNORE
    assert "个人来信" in signals(m)


def test_self_sent_is_not_personal():
    """自己发给自己不算"真人来信"——否则判定层会给自己推通知。"""
    m = mail("test", "test", frm="me@gmail.com")
    m["to"] = "me@gmail.com"
    assert is_self_sent(m) is True
    assert "个人来信" not in signals(m)


def test_personal_with_strong_signal_still_now():
    """个人邮箱 + 面试关键词 → 照常 NOW。"""
    m = mail("面试邀请", "请安排时间", frm="hr@company.com")
    m["from"] = "someone@gmail.com"
    assert classify(m) == NOW


def test_corp_bulk_without_signal_can_be_ignored():
    """机构群发无信号 → 可以沉底（与个人来信区别对待）。"""
    m = mail("Weekly update", "nothing actionable",
             frm="news@bigcorp.example.com")
    assert classify(m) == IGNORE


def test_addr_extraction():
    assert _addr("Name <a@b.com>") == "a@b.com"
    assert _addr("a@b.com") == "a@b.com"
    assert _addr("") == ""


# ── 真实验收发现的漏报（必须守住）──

def test_ci_failure_is_not_ignored():
    """GitHub CI 挂了不该被忽略——真实验收时发现 4 封被误杀。"""
    m = mail("[repo] Run failed: CI - main", "The workflow failed.",
             frm="notifications@github.com")
    assert classify(m) != IGNORE
    assert "构建异常" in signals(m)


def test_invitation_is_not_ignored():
    """母校邀请信不该被忽略——真实验收时发现 2 封被误杀。"""
    m = mail("致2025届高明翰同学的一封毕业生邀请信", "邀请您参加",
             frm="invitation@mycoss.example.com")
    assert classify(m) != IGNORE
    assert "邀请问卷" in signals(m)


def test_survey_request_is_not_ignored():
    m = mail("母校再次邀请您积极参与评价", "请填写问卷",
             frm="invitation@mycoss.example.com")
    assert classify(m) != IGNORE


# ── BC-016：线上跑一天暴露的两处误报，必须守住 ──

def test_handling_fee_is_not_renewal():
    """「手续费」包含「续费」子串——中文没有词边界，这是踩过的坑。

    实测：ZA Bank 的「淘宝 0 手续费优惠」因此被误判成订阅到期。
    """
    m = mail("淘宝 0 手续费优惠 扫货更划算", "各种促销内容")
    assert "订阅时限" not in signals(m)
    assert classify(m) != NOW


def test_real_renewal_still_caught():
    """修掉误报的同时，真的续费提醒不能被误伤。"""
    m = mail("您的会员即将续费", "将于明日扣款")
    assert "订阅时限" in signals(m)


def test_interview_article_is_not_interview_invitation():
    """麦肯锡的访谈文章不是面试通知。

    实测：「The power of purpose, culture, and grit: An interview with...」
    单独出现 interview 会误判。必须要求搭配动作词。
    """
    m = mail("The power of purpose, culture, and grit: An interview with the CEO",
             "In this interview, he shares his views.",
             frm="publishing@email.mckinsey.com")
    assert "面试进展" not in signals(m)
    assert classify(m) != NOW


def test_real_interview_invitation_still_caught():
    """真的面试邀请不能被上面那条规则误伤。"""
    for subj in ["Interview invitation from ByteDance",
                 "We'd like to schedule an interview with you",
                 "面试邀请：请确认时间"]:
        assert "面试进展" in signals(mail(subj, "")), subj


def test_strong_signal_looks_at_subject_only():
    """强信号只扫主题：正文里的关键词不该把邮件抬进 NOW。

    营销邮件正文动辄几千字，扫全文必然误触发（BC-016 的根因）。
    """
    m = mail("本周精选好文推荐",
             "顺便提一句，您的 payment was declined，不过这是正文测试内容")
    assert classify(m) != NOW, "正文里的关键词不该触发 NOW"


def test_weak_signal_still_scans_body():
    """弱信号仍扫全文——它只进汇总，宁可宽一些。"""
    m = mail("本周动态", "您有一笔新的账单已生成")
    assert "账务变动" in signals(m)
