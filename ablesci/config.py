"""Environment configuration; validation never prints secret values."""
from __future__ import annotations

import json
import os
import re

from .models import Account

MAX_ACCOUNT_SLOTS = 20


class ConfigError(ValueError):
    """Invalid user configuration."""


def clean_value(value: str, *, strip_whitespace: bool) -> str:
    value = value.replace("\ufeff", "").strip("\r\n")
    return value.strip() if strip_whitespace else value


def read_env(name: str, *, strip_whitespace: bool = True) -> str:
    return clean_value(os.environ.get(name, ""), strip_whitespace=strip_whitespace)


def collect_accounts() -> list[Account]:
    """Merge JSON, numbered slots and legacy settings, rejecting conflicting duplicates."""
    accounts: list[Account] = []
    seen: dict[str, Account] = {}

    def add(email: str, password: str, label: str, source: str) -> None:
        email = clean_value(email, strip_whitespace=True)
        password = clean_value(password, strip_whitespace=False)
        if not email or not password:
            raise ConfigError(f"{source} 配置不完整：邮箱和密码必须同时提供")
        if "@" not in email or any(c.isspace() for c in email):
            raise ConfigError(f"{source} 邮箱格式无效")
        key = email.casefold()
        if key in seen:
            if seen[key].password != password:
                raise ConfigError(f"{source} 与其他配置重复且密码不一致，请只保留一处")
            return
        label = " ".join(label.split()) or f"账号{len(accounts) + 1}"
        label = label.replace(password, "***").replace(email, "***")
        label = re.sub(r"[^\s@]+@[^\s@]+", "***", label)
        account = Account(label, email, password)
        seen[key] = account
        accounts.append(account)

    raw = read_env("ABLESCI_ACCOUNTS_JSON")
    if raw:
        try:
            items = json.loads(raw)
        except ValueError:
            raise ConfigError("ABLESCI_ACCOUNTS_JSON 不是有效 JSON，请使用双引号且不要带尾随逗号") from None
        if not isinstance(items, list) or not items:
            raise ConfigError("ABLESCI_ACCOUNTS_JSON 必须是非空数组")
        for i, item in enumerate(items, 1):
            source = f"ABLESCI_ACCOUNTS_JSON 第 {i} 项"
            if not isinstance(item, dict) or any(
                not isinstance(item.get(k, ""), str) for k in ("email", "password", "name")
            ):
                raise ConfigError(f"{source} 必须是对象，email/password/name 必须是字符串")
            add(item.get("email", ""), item.get("password", ""), item.get("name", ""), source)

    for i in range(1, MAX_ACCOUNT_SLOTS + 1):
        email = read_env(f"ABLESCI_{i}_EMAIL")
        password = read_env(f"ABLESCI_{i}_PASSWORD", strip_whitespace=False)
        if email or password:
            add(email, password, read_env(f"ABLESCI_{i}_NAME") or f"账号{i}", f"ABLESCI_{i}_*")

    email = read_env("ABLESCI_EMAIL")
    password = read_env("ABLESCI_PASSWORD", strip_whitespace=False)
    if email or password:
        add(email, password, "默认账号", "ABLESCI_EMAIL / ABLESCI_PASSWORD")
    if not accounts:
        raise ConfigError("没有账号配置，请添加 ABLESCI_1_EMAIL / ABLESCI_1_PASSWORD 或 ABLESCI_ACCOUNTS_JSON")
    if len(accounts) > MAX_ACCOUNT_SLOTS:
        raise ConfigError(f"最多支持 {MAX_ACCOUNT_SLOTS} 个不同账号")
    return accounts


def jitter_limit() -> int:
    raw = read_env("ABLESCI_JITTER_MAX") or "0"
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError("ABLESCI_JITTER_MAX 必须是 0～1500 的整数（秒）") from None
    if not 0 <= value <= 1500:
        raise ConfigError("ABLESCI_JITTER_MAX 必须在 0～1500 秒之间")
    return value
