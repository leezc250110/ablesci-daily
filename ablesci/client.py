from __future__ import annotations
import re
from html.parser import HTMLParser
import requests

BASE = "https://www.ablesci.com"
LOGIN_URL = f"{BASE}/site/login"
SIGN_URL = f"{BASE}/user/sign"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DOC_HEADERS = {
    "User-Agent": UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="126", "Not:A-Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
XHR_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="126", "Not:A-Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
TIMEOUT = 25
POINT_PATTERNS = (
    re.compile(r"当前拥有<[^>]*>\s*(\d+)\s*</cite>\s*积分"),
    re.compile(r"当前拥有[^0-9]{0,80}?(\d+)[^0-9]{0,20}?积分"),
)
STREAK_PATTERNS = (
    re.compile(r"已连续签到<[^>]*>\s*(\d+)\s*</cite>"),
    re.compile(r"已连续签到[^0-9]{0,80}?(\d+)"),
)


def find_first(patterns, text):
    for pat in patterns:
        m = pat.search(text)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


class ResponseError(RuntimeError):
    """Unexpected site response, without including response bodies in logs."""


class CSRFParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.form_token = None
        self.meta_token = None
        self.legacy_token = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "_csrf":
            self.form_token = attrs.get("value") or self.form_token
        if tag == "meta" and attrs.get("name") == "csrf-token":
            self.meta_token = attrs.get("content") or self.meta_token
        if attrs.get("id") == "csrf-val":
            self.legacy_token = attrs.get("value") or self.legacy_token


def extract_csrf(page: str) -> str:
    parser = CSRFParser()
    parser.feed(page)
    token = parser.form_token or parser.meta_token or parser.legacy_token
    if not token or not token.strip():
        raise ResponseError("登录页未找到 CSRF token，请检查站点结构或网络拦截")
    return token.strip()


def parse_json(resp) -> dict:
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        raise ResponseError(f"站点返回非 JSON 响应（HTTP {resp.status_code}）") from None
    if not isinstance(data, dict) or type(data.get("code")) is not int:
        raise ResponseError("站点返回的数据结构无效（需要对象和整数 code）")
    if not isinstance(data.get("msg", ""), str):
        raise ResponseError("站点返回的 msg 类型无效")
    return data


class AbleSciClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(DOC_HEADERS)

    def fresh_csrf(self) -> str:
        """每次都重新 GET 登录页并抓取当次有效的 token。"""
        resp = self.session.get(
            LOGIN_URL, headers={"Referer": BASE + "/"}, timeout=TIMEOUT
        )
        resp.raise_for_status()
        return extract_csrf(resp.text)

    def login(self, email: str, password: str) -> dict:
        csrf = self.fresh_csrf()
        headers = dict(XHR_HEADERS)
        headers["Referer"] = LOGIN_URL
        headers["Origin"] = BASE
        resp = self.session.post(
            LOGIN_URL,
            data={"_csrf": csrf, "email": email, "password": password},
            headers=headers,
            timeout=TIMEOUT,
        )
        return parse_json(resp)

    def sync(self) -> None:
        """登录后访问首页，让服务端会话状态落定。"""
        resp = self.session.get(BASE + "/", headers={"Referer": LOGIN_URL}, timeout=TIMEOUT)
        resp.raise_for_status()

    def sign(self) -> dict:
        headers = dict(XHR_HEADERS)
        headers["Referer"] = BASE + "/"
        resp = self.session.get(SIGN_URL, headers=headers, timeout=TIMEOUT)
        return parse_json(resp)

    def stats(self) -> tuple[str | None, str | None]:
        """读取积分与连续签到天数；解析不到不算失败。"""
        try:
            resp = self.session.get(BASE + "/", timeout=TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException:
            return None, None
        return (
            find_first(POINT_PATTERNS, resp.text),
            find_first(STREAK_PATTERNS, resp.text),
        )

    def close(self) -> None:
        self.session.close()
