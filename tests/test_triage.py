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
    _domain, classify, load_weights, record_feedback, signals, triage,
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
    """真人来信即使没命中任何信号，也进汇总而不是忽略。"""
    m = mail("hi", "just saying hello", frm="friend@example.com")
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
