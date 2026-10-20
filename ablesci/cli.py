"""Command-line orchestration, with offline configuration validation."""
from __future__ import annotations

import argparse
import os
import random
import time

import requests

from .client import AbleSciClient, ResponseError
from .config import ConfigError, collect_accounts, jitter_limit
from .models import OK, ALREADY
from .notifications import send_mail
from .reports import print_report, write_step_summary
from .runner import run_account


def check_site() -> int:
    client = AbleSciClient()
    try:
        client.fresh_csrf()
    except (requests.RequestException, ResponseError) as exc:
        print(f"❌ 站点自检失败（{type(exc).__name__}），请检查网络或站点结构")
        return 1
    finally:
        client.close()
    print("✅ 站点可达，CSRF 提取成功（未登录，未执行签到）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AbleSci 多账号每日签到")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="联网检查登录页，不需要账号")
    mode.add_argument("--check-config", action="store_true", help="离线检查账号和延迟配置，不登录、不发邮件")
    args = parser.parse_args(argv)
    if args.check:
        return check_site()
    try:
        accounts = collect_accounts()
        jitter = jitter_limit()
    except ConfigError as exc:
        print(f"❌ 配置错误：{exc}")
        return 1
    print(f"✅ 账号配置检查通过，共 {len(accounts)} 个账号")
    if args.check_config:
        return 0
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and jitter:
        wait = random.randint(0, jitter)
        print(f"⏱ 随机等待 {wait} 秒")
        time.sleep(wait)
    outcomes = []
    for idx, account in enumerate(accounts):
        if idx:
            time.sleep(random.uniform(4, 15))
        # Use slot numbers until the sanitised report is built.
        print(f"正在处理账号 {idx + 1}/{len(accounts)}……")
        outcomes.append(run_account(account))
    print_report(outcomes)
    write_step_summary(outcomes)
    send_mail(outcomes)
    return int(any(o.status not in (OK, ALREADY) for o in outcomes))
