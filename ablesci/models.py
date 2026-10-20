from __future__ import annotations
from dataclasses import dataclass, field

OK = "ok"            # 签到成功
ALREADY = "already"  # 今天已经签过
FAILED = "failed"    # 站点明确拒绝（密码错等）
CAPTCHA = "captcha"  # 被要求输入验证码
ERROR = "error"      # 网络/解析等异常


def mask_email(email: str) -> str:
    """打码邮箱，避免公开仓库的 Actions 日志泄露账号。"""
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    head = local[0] if len(local) <= 2 else local[:2]
    return f"{head}***@{domain}"


@dataclass
class Account:
    label: str
    email: str = field(repr=False)
    password: str = field(repr=False)

    @property
    def display(self) -> str:
        return f"{self.label} ({mask_email(self.email)})"


@dataclass
class Outcome:
    account: Account
    status: str
    message: str
    points: str | None = None
    streak: str | None = None
STATUS_ICON = {
    OK: "✅",
    ALREADY: "ℹ️",
    FAILED: "❌",
    CAPTCHA: "🤖",
    ERROR: "⚠️",
}
STATUS_TEXT = {
    OK: "签到成功",
    ALREADY: "今日已签到",
    FAILED: "失败",
    CAPTCHA: "被要求验证码",
    ERROR: "异常",
}
