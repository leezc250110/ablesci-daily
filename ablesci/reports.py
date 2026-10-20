from __future__ import annotations
import html
import os
import time
from .models import Outcome, OK, ALREADY, STATUS_ICON, STATUS_TEXT

def print_report(outcomes: list[Outcome]) -> None:
    print("\n" + "=" * 62)
    print("AbleSci 签到结果汇总")
    print("=" * 62)
    for o in outcomes:
        icon = STATUS_ICON.get(o.status, "?")
        print(f"\n{icon} {o.account.display} —— {STATUS_TEXT.get(o.status, o.status)}")
        print(f"   说明：{o.message}")
        if o.points is not None:
            print(f"   当前积分：{o.points}")
        if o.streak is not None:
            print(f"   连续签到：{o.streak} 天")
    print("\n" + "=" * 62)


def markdown_cell(value: str) -> str:
    return html.escape(" ".join(str(value).split())).replace("|", "&#124;")


def write_step_summary(outcomes: list[Outcome]) -> None:
    """写到 GitHub Actions 的 Job Summary，在网页上直接可看。"""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("## AbleSci 每日签到结果\n\n")
            fh.write("| 账号 | 状态 | 说明 | 积分 | 连签 |\n")
            fh.write("| --- | --- | --- | --- | --- |\n")
            for o in outcomes:
                icon = STATUS_ICON.get(o.status, "?")
                msg = markdown_cell(o.message)
                fh.write(
                    f"| {markdown_cell(o.account.display)} | {icon} {STATUS_TEXT.get(o.status, o.status)} "
                    f"| {msg} | {o.points or '-'} | {o.streak or '-'} |\n"
                )
    except OSError as exc:
        print(f"（写入 Step Summary 失败：{exc}）")


def build_subject(outcomes: list[Outcome]) -> str:
    total = len(outcomes)
    ok = sum(1 for o in outcomes if o.status in (OK, ALREADY))
    stamp = time.strftime("%m-%d %H:%M")
    if ok == total:
        return f"✅ AbleSci 签到成功 {ok}/{total}（{stamp}）"
    return f"❌ AbleSci 签到异常 {total - ok}/{total}（{stamp}）"


def build_bodies(outcomes: list[Outcome]) -> tuple[str, str]:
    """返回 (纯文本, HTML) 两份正文。"""
    lines = ["AbleSci 每日签到结果", "=" * 34, ""]
    for o in outcomes:
        lines.append(
            f"{STATUS_ICON.get(o.status, '?')} {o.account.display}"
            f" —— {STATUS_TEXT.get(o.status, o.status)}"
        )
        lines.append(f"   {o.message}")
        if o.points is not None:
            lines.append(f"   当前积分：{o.points}")
        if o.streak is not None:
            lines.append(f"   连续签到：{o.streak} 天")
        lines.append("")
    text_body = "\n".join(lines)

    cells = []
    for o in outcomes:
        cells.append(
            "<tr>"
            f'<td style="padding:8px;border-bottom:1px solid #eee">{html.escape(o.account.display)}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">'
            f'{STATUS_ICON.get(o.status, "?")} {html.escape(STATUS_TEXT.get(o.status, o.status))}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #eee">{html.escape(o.message)}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{html.escape(o.points or "-")}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{html.escape(o.streak or "-")}</td>'
            "</tr>"
        )
    html_body = (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,'
        '\'Helvetica Neue\',Arial,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;color:#222">'
        f'<h2 style="margin:0 0 4px">{html.escape(build_subject(outcomes))}</h2>'
        '<p style="color:#888;margin:0 0 16px;font-size:13px">由 GitHub Actions 自动发送</p>'
        '<table style="border-collapse:collapse;font-size:14px">'
        '<thead><tr style="background:#f6f8fa">'
        '<th style="padding:8px;text-align:left">账号</th>'
        '<th style="padding:8px;text-align:left">状态</th>'
        '<th style="padding:8px;text-align:left">说明</th>'
        '<th style="padding:8px;text-align:right">积分</th>'
        '<th style="padding:8px;text-align:right">连签</th>'
        "</tr></thead><tbody>"
        + "".join(cells)
        + "</tbody></table></div>"
    )
    return text_body, html_body
