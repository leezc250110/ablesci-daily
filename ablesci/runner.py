"""Isolated sessions and bounded retries for each account."""
from __future__ import annotations

import re
import time

import requests

from .client import AbleSciClient, ResponseError
from .models import Account, Outcome, OK, ALREADY, FAILED, CAPTCHA, ERROR


def site_message(value: str, account: Account) -> str:
    """Redact credentials and email addresses before any output channel sees them."""
    for secret in sorted((account.password, account.email), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "***")
    value = re.sub(r"[^\s<>\"'@]+@[^\s<>\"'@]+", "***", value)
    return " ".join(value.split())[:300]


def run_account(account: Account, max_attempts: int = 2) -> Outcome:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    last = Outcome(account, ERROR, "未能完成签到")
    for attempt in range(max_attempts):
        if attempt:
            time.sleep(3)
        client = AbleSciClient()
        phase = "登录"
        try:
            result = client.login(account.email, account.password)
            msg = result.get("msg", "")
            if result.get("verify") in (1, "1", True) or "验证码" in msg:
                return Outcome(account, CAPTCHA, "站点要求验证码；请在浏览器完成验证后再手动运行")
            if result["code"] != 0:
                return Outcome(account, FAILED, "登录失败：" + site_message(msg or "未知错误", account))
            phase = "签到"
            client.sync()
            result = client.sign()
            msg = result.get("msg", "")
            if "验证码" in msg:
                return Outcome(account, CAPTCHA, "签到需要验证码；请在浏览器完成验证")
            if result["code"] == 1 and "需要登录" in msg:
                last = Outcome(account, ERROR, "登录态未保持")
                continue
            if result["code"] == 0:
                status, message = OK, msg or "签到成功"
            elif result["code"] == 1 and re.search(r"(?:今日|今天)(?:已经|已)(?:签到|于)|已经签到|已签到", msg):
                status = ALREADY
                message = re.sub(r"^签到失败[，,、:：]?\s*", "", msg).strip()
            else:
                status, message = FAILED, "签到失败：" + (msg or "未知错误")
            points, streak = client.stats()
            return Outcome(account, status, site_message(message, account), points, streak)
        except ResponseError as exc:
            return Outcome(account, ERROR, str(exc))
        except requests.RequestException as exc:
            # Never print exception text: it can contain URLs or response content.
            last = Outcome(account, ERROR, f"{phase}网络异常（{type(exc).__name__}）")
            # A sign request may already have taken effect; leave verification to the next run.
            if phase != "登录":
                return last
        finally:
            client.close()
    return last
