from __future__ import annotations
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from .config import read_env
from .models import Outcome, FAILED, CAPTCHA, ERROR, mask_email
from .reports import build_subject, build_bodies

MAIL_WHEN_VALUES = ("always", "failure", "never")


def mail_config() -> dict | None:
    """读取邮件配置。三个必填项不齐时返回 None（视为未启用）。"""
    host = read_env("SMTP_HOST", strip_whitespace=True)
    user = read_env("SMTP_USER", strip_whitespace=True)
    password = read_env("SMTP_PASS", strip_whitespace=False)

    missing = [
        name
        for name, value in (("SMTP_HOST", host), ("SMTP_USER", user), ("SMTP_PASS", password))
        if not value
    ]
    if missing:
        if len(missing) < 3:  # 配了一部分才算"配置错误"，全空是正常的
            print(f"⚠️  邮件配置不完整，缺少 {'、'.join(missing)}，已跳过邮件通知")
        return None

    port_raw = read_env("SMTP_PORT", strip_whitespace=True)
    try:
        port = int(port_raw) if port_raw else 465
    except ValueError:
        print("⚠️  SMTP_PORT 不是整数，已回退到 465")
        port = 465

    if port not in (465, 587):
        print("⚠️ SMTP_PORT 仅支持 465 或 587，已跳过邮件通知")
        return None

    to_raw = read_env("MAIL_TO", strip_whitespace=True)
    recipients = [a.strip() for a in to_raw.replace(";", ",").split(",") if a.strip()]
    if not recipients:
        recipients = [user]

    when = (read_env("MAIL_WHEN", strip_whitespace=True) or "always").lower()
    if when not in MAIL_WHEN_VALUES:
        print("⚠️  MAIL_WHEN 取值无效，已回退到 always")
        when = "always"

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "recipients": recipients,
        "when": when,
    }


def send_mail(outcomes: list[Outcome]) -> None:
    """发送签到结果邮件。任何失败都只告警，不影响签到本身的退出码。"""
    cfg = mail_config()
    if cfg is None:
        return

    if cfg["when"] == "never":
        print("（MAIL_WHEN=never，已跳过邮件通知）")
        return

    failed = [o for o in outcomes if o.status in (FAILED, CAPTCHA, ERROR)]
    if cfg["when"] == "failure" and not failed:
        print("（MAIL_WHEN=failure 且本次全部成功，已跳过邮件通知）")
        return

    try:
        subject = build_subject(outcomes)
        text_body, html_body = build_bodies(outcomes)

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = cfg["user"]
        message["To"] = ", ".join(cfg["recipients"])
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid()
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30, context=ssl.create_default_context()) as server:
                server.login(cfg["user"], cfg["password"])
                server.send_message(message)
        else:
            # 587 走 STARTTLS；注意 25 端口在 Azure 上是被封锁的
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.send_message(message)
    except Exception as exc:  # noqa: BLE001 - 通知失败绝不能让签到任务变红
        print(f"⚠️  邮件发送失败（不影响签到结果）：{type(exc).__name__}（请检查 SMTP 配置和服务状态）")
        return

    shown = "、".join(mask_email(r) for r in cfg["recipients"])
    print(f"📧 邮件已发送至 {shown}")
