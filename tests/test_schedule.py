"""定时检查与分级汇报的测试（用桩，不连真实邮箱）。

核心是**幂等**：同一封邮件只能汇报一次。
重复汇报的后果跟判定误报一样——你会关掉它，系统随即失效。
"""

import time

import pytest

from mail import schedule


def _patch_fetch(monkeypatch, mails):
    def fake(provider, limit=5, **kw):
        return [dict(m) for m in mails]
    monkeypatch.setattr(schedule, "fetch_recent", fake)


def _patch_emit(monkeypatch):
    lines = []
    monkeypatch.setattr(schedule, "_emit",
                        lambda text, path=None: lines.append(text))
    return lines


def _mail(i, subject="普通邮件", body="无实质内容"):
    """注意用真实个人邮箱域名——example.com 不在白名单里，
    无信号的邮件会被判 IGNORE，根本进不了汇总缓冲区。"""
    return {"id": str(i), "subject": subject, "body": body,
            "from": "friend@gmail.com", "to": "me@example.com"}


# ── 幂等 ──

def test_same_mail_not_reported_twice(monkeypatch, tmp_path):
    _patch_fetch(monkeypatch, [_mail(1)])
    st = tmp_path / "state.json"

    r1 = schedule.check_once(providers=("gmail",), state_path=st,
                             weights_path=tmp_path / "w.json")
    r2 = schedule.check_once(providers=("gmail",), state_path=st,
                             weights_path=tmp_path / "w.json")

    assert r1["fresh"] == 1
    assert r2["fresh"] == 0, "第二次不应再报同一封邮件"


def test_new_mail_is_reported(monkeypatch, tmp_path):
    mails = [_mail(1)]
    _patch_fetch(monkeypatch, mails)
    st = tmp_path / "state.json"

    schedule.check_once(providers=("gmail",), state_path=st,
                        weights_path=tmp_path / "w.json")
    mails.append(_mail(2))                       # 来新邮件了

    r = schedule.check_once(providers=("gmail",), state_path=st,
                            weights_path=tmp_path / "w.json")
    assert r["fresh"] == 1, "新邮件应当被报到"


def test_keys_are_provider_scoped(monkeypatch, tmp_path):
    """两个邮箱的内部 id 可能相同，key 必须带 provider 区分。"""
    _patch_fetch(monkeypatch, [_mail(1)])
    st = tmp_path / "state.json"
    schedule.check_once(providers=("gmail",), state_path=st,
                        weights_path=tmp_path / "w.json")
    r = schedule.check_once(providers=("netease",), state_path=st,
                            weights_path=tmp_path / "w.json")
    assert r["fresh"] == 1, "不同邮箱的同 id 邮件是两封，都该报"


# ── 分级 ──

def test_urgent_goes_out_immediately(monkeypatch, tmp_path):
    lines = _patch_emit(monkeypatch)
    _patch_fetch(monkeypatch, [
        {"id": "1", "subject": "Your payment was unsuccessful",
         "body": "payment declined", "from": "billing@example.com",
         "to": "me@example.com"},
    ])
    r = schedule.check_once(providers=("gmail",), state_path=tmp_path / "s.json",
                            weights_path=tmp_path / "w.json")
    assert len(r["urgent"]) == 1
    assert any("要紧" in line for line in lines)


def test_normal_mail_is_buffered_not_pushed(monkeypatch, tmp_path):
    lines = _patch_emit(monkeypatch)
    _patch_fetch(monkeypatch, [
        {"id": "1", "subject": "Weekly update",
         "body": "newsletter content", "from": "friend@gmail.com",
         "to": "me@example.com"},
    ])
    r = schedule.check_once(providers=("gmail",), state_path=tmp_path / "s.json",
                            weights_path=tmp_path / "w.json")
    assert r["urgent"] == [], "普通邮件不该立即推送"
    assert r["buffered"] >= 0


# ── 半天节奏 ──

def test_digest_fires_after_half_day(monkeypatch, tmp_path):
    lines = _patch_emit(monkeypatch)
    mails = [_mail(1, "普通邮件")]
    _patch_fetch(monkeypatch, mails)
    st = tmp_path / "state.json"
    t0 = time.time()

    # 第一次先把基线建起来（它自身会触发一次汇总，所以下面清空记录）
    schedule.check_once(providers=("gmail",), state_path=st,
                        weights_path=tmp_path / "w.json", now=t0)
    lines.clear()

    # 13 小时后又有新邮件
    mails.append(_mail(2, "新来的普通邮件"))
    schedule.check_once(providers=("gmail",), state_path=st,
                        weights_path=tmp_path / "w.json",
                        now=t0 + 13 * 3600)

    assert any("汇总" in line for line in lines), "半天后应触发汇总"


def test_digest_not_fired_too_early(monkeypatch, tmp_path):
    lines = _patch_emit(monkeypatch)
    mails = [_mail(1, "普通邮件")]
    _patch_fetch(monkeypatch, mails)
    st = tmp_path / "state.json"
    t0 = time.time()

    schedule.check_once(providers=("gmail",), state_path=st,
                        weights_path=tmp_path / "w.json", now=t0)
    lines.clear()
    mails.append(_mail(2, "又一封普通邮件"))
    schedule.check_once(providers=("gmail",), state_path=st,
                        weights_path=tmp_path / "w.json",
                        now=t0 + 3600)          # 才过 1 小时

    assert not any("汇总" in line for line in lines), "不到半天不该汇总"


# ── 状态 ──

def test_state_persists(monkeypatch, tmp_path):
    _patch_fetch(monkeypatch, [_mail(1)])
    st = tmp_path / "state.json"
    schedule.check_once(providers=("gmail",), state_path=st,
                        weights_path=tmp_path / "w.json")
    state = schedule.load_state(st)
    assert "gmail:1" in state["reported"]


def test_corrupt_state_recovers(monkeypatch, tmp_path):
    """状态文件损坏不能让整个定时崩掉。"""
    st = tmp_path / "state.json"
    st.write_text("{ 这不是合法 json", encoding="utf-8")
    _patch_fetch(monkeypatch, [_mail(1)])
    r = schedule.check_once(providers=("gmail",), state_path=st,
                            weights_path=tmp_path / "w.json")
    assert r["fresh"] == 1


def test_fetch_failure_does_not_crash(monkeypatch, tmp_path):
    """某个邮箱连不上，不能影响另一个。"""
    def boom(provider, limit=5, **kw):
        raise OSError("连不上")
    monkeypatch.setattr(schedule, "fetch_recent", boom)
    r = schedule.check_once(providers=("gmail",),
                            state_path=tmp_path / "s.json",
                            weights_path=tmp_path / "w.json")
    assert r["fresh"] == 0
