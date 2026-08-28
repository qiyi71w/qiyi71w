#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

GRAPHQL = "https://api.github.com/graphql"
USERNAME = "qiyi71w"
DAYS = 40


def graphql(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "qiyi71w-profile-activity-graph",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], ensure_ascii=False))
    return payload["data"]


def contribution_days(token: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    data = graphql(
        query,
        {"login": USERNAME, "from": start.isoformat(), "to": now.isoformat()},
        token,
    )
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [day for week in weeks for day in week["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    return days[-DAYS:]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render(days: list[dict], dark: bool) -> str:
    width, height = 860, 230
    left, right, top, bottom = 52, 824, 54, 174
    plot_w, plot_h = right - left, bottom - top
    counts = [int(d["contributionCount"]) for d in days]
    max_count = max(max(counts, default=0), 1)
    total = sum(counts)
    active = sum(1 for count in counts if count > 0)
    peak = max(counts, default=0)

    if dark:
        bg, border, text, muted, grid = "#0d1117", "#30363d", "#f0f6fc", "#8b949e", "#21262d"
        line, area = "#3fb950", "#238636"
    else:
        bg, border, text, muted, grid = "#ffffff", "#d0d7de", "#1f2328", "#656d76", "#d8dee4"
        line, area = "#2da44e", "#dafbe1"

    n = max(len(days), 1)
    points: list[tuple[float, float]] = []
    for index, count in enumerate(counts):
        x = left if n == 1 else left + (plot_w * index / (n - 1))
        y = bottom - (plot_h * count / max_count)
        points.append((x, y))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    if points:
        area_points = f"{left},{bottom} {polyline} {right},{bottom}"
    else:
        area_points = f"{left},{bottom} {right},{bottom}"

    y_ticks = sorted({0, max_count // 2, max_count})
    grid_parts = []
    for tick in y_ticks:
        y = bottom - (plot_h * tick / max_count)
        grid_parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" class="axis">{tick}</text>'
        )

    labels = []
    if days:
        indexes = sorted({0, 7, 14, 21, 28, 35, len(days) - 1})
        for index in indexes:
            if index >= len(days):
                continue
            x = left if len(days) == 1 else left + (plot_w * index / (len(days) - 1))
            date = datetime.strptime(days[index]["date"], "%Y-%m-%d")
            labels.append(
                f'<text x="{x:.1f}" y="198" text-anchor="middle" class="axis">{date.strftime("%b %d")}</text>'
            )

    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{line}"/>'
        for x, y in points
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
.title{{fill:{text};font:600 15px Arial,sans-serif}}
.meta{{fill:{muted};font:400 11px Arial,sans-serif}}
.axis{{fill:{muted};font:400 9px Arial,sans-serif}}
</style>
<rect x="0.5" y="0.5" width="859" height="229" rx="12" fill="{bg}" stroke="{border}"/>
<text class="title" x="24" y="30">Contribution activity · last {DAYS} days</text>
<text class="meta" x="836" y="30" text-anchor="end">{total} contributions · {active} active days · peak {peak}</text>
{''.join(grid_parts)}
<polygon points="{area_points}" fill="{area}" opacity="0.55"/>
<polyline points="{polyline}" fill="none" stroke="{line}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
{circles}
{''.join(labels)}
</svg>'''


def main() -> None:
    token = os.getenv("METRICS_TOKEN")
    if not token:
        raise SystemExit("METRICS_TOKEN is required")
    days = contribution_days(token)
    Path("assets").mkdir(exist_ok=True)
    Path("assets/activity-graph.svg").write_text(render(days, dark=False), encoding="utf-8")
    Path("assets/activity-graph-dark.svg").write_text(render(days, dark=True), encoding="utf-8")


if __name__ == "__main__":
    main()
