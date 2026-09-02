"""
mail/adapter.py — 邮件信息源适配器（adapter 生态的第一个实现）

为什么做成 adapter 而不是"邮件功能"：
将来要接本地文件、微知、RSS、日历时，若每个都写一套，判定与呈现层
就要重写 N 遍。统一成 adapter 后，每个适配器只负责
「把原始数据捞出来 → 转成标准结构」，上层共用一套判定与汇报。

安全约束（写进代码，不靠自觉）：
- 凭证**只从环境变量读取**，绝不硬编码、绝不写进日志或异常信息
- 收取时用 **readonly 模式**，不把邮件标记为已读
- 发送必须显式调用，没有任何自动发送路径
"""

from __future__ import annotations

import imaplib
import os
import smtplib
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser

# 各服务商的服务器地址与连接方式
#   smtp_ssl=True  -> SMTP_SSL（465）
#   smtp_ssl=False -> SMTP + STARTTLS（587）
PROVIDERS = {
    "gmail": {
        "imap": ("imap.gmail.com", 993),
        "smtp": ("smtp.gmail.com", 587),
        "smtp_ssl": False,
    },
    "netease": {
        "imap": ("imap.163.com", 993),
        "smtp": ("smtp.163.com", 465),
        "smtp_ssl": True,
    },
}

# 环境变量名：地址 / 口令（Gmail 是应用专用密码，163 是授权码）
_ENV = {
    "gmail":   ("GMAIL_ADDRESS",   "GMAIL_APP_PASSWORD"),
    "netease": ("NETEASE_ADDRESS", "NETEASE_AUTH_CODE"),
}


class MailConfigError(RuntimeError):
    """凭证缺失或配置错误。错误信息里**不含**任何凭证内容。"""


def _creds(provider: str) -> tuple[str, str]:
    """读取凭证。缺什么说清楚，但绝不回显已填的那一项。"""
    if provider not in PROVIDERS:
        raise MailConfigError(f"未知服务商 {provider!r}，可选：{list(PROVIDERS)}")
    addr_key, pwd_key = _ENV[provider]
    addr, pwd = os.environ.get(addr_key, "").strip(), os.environ.get(pwd_key, "").strip()
    missing = [k for k, v in ((addr_key, addr), (pwd_key, pwd)) if not v]
    if missing:
        raise MailConfigError(
            f"{provider} 凭证缺失：{', '.join(missing)} 未设置。"
            f"请写到项目根目录 .env（该文件已被 gitignore）"
        )
    return addr, pwd


def _decode(value: str | None) -> str:
    """解码邮件头（中文主题通常是 base64 编码的）。"""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _body(msg, limit: int = 400) -> str:
    """取纯文本正文优先，没有则退 HTML 去标签。"""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        content = part.get_content()
    except Exception:
        return ""
    if part.get_content_subtype() == "html":
        import re
        content = re.sub(r"<[^>]+>", " ", content)
    return " ".join(content.split())[:limit]


def fetch_recent(provider: str, limit: int = 5, folder: str = "INBOX") -> list[dict]:
    """拉取最近 N 封邮件。**只读**，不会把邮件标为已读。"""
    addr, pwd = _creds(provider)
    host, port = PROVIDERS[provider]["imap"]

    out: list[dict] = []
    with imaplib.IMAP4_SSL(host, port) as m:
        m.login(addr, pwd)
        # readonly=True 是关键：避免"看一眼"就把未读变已读
        typ, _ = m.select(folder, readonly=True)
        if typ != "OK":
            raise MailConfigError(f"无法打开 {folder}（服务商 {provider}）")

        typ, data = m.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []

        ids = data[0].split()[-limit:]
        parser = BytesParser(policy=policy.default)
        for num in reversed(ids):                      # 新的在前
            typ, raw = m.fetch(num, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = parser.parsebytes(raw[0][1])
            out.append({
                "id":      num.decode(),
                "from":    _decode(msg.get("From")),
                "to":      _decode(msg.get("To")),
                "subject": _decode(msg.get("Subject")) or "(无主题)",
                "date":    _decode(msg.get("Date")),
                "body":    _body(msg),
            })
    return out


def send(provider: str, to: str, subject: str, body: str) -> None:
    """发送一封纯文本邮件。**必须显式调用**，无自动发送路径。"""
    addr, pwd = _creds(provider)
    host, port = PROVIDERS[provider]["imap"][0], PROVIDERS[provider]["smtp"][0]
    smtp_host, smtp_port = PROVIDERS[provider]["smtp"]
    ssl = PROVIDERS[provider]["smtp_ssl"]

    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = addr, to, subject
    msg.set_content(body)

    if ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as s:
            s.login(addr, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(addr, pwd)
            s.send_message(msg)
