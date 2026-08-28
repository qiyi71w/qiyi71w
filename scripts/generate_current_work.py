#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"

def api_get(path, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-profile-current-work",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def search(query, token, sort=None, order=None, per_page=1):
    p = {"q": query, "per_page": str(per_page)}
    if sort: p["sort"] = sort
    if order: p["order"] = order
    return api_get("/search/issues?" + urllib.parse.urlencode(p), token)

def esc(v):
    return html.escape(str(v), quote=True)

def shorten(v, n=70):
    v = " ".join(str(v or "").split())
    return v if len(v) <= n else v[:n-1].rstrip() + "…"

def ago(iso):
    if not iso: return "unknown"
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    sec = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    if sec < 60: return "just now"
    if sec < 3600: return f"{sec // 60}m ago"
    if sec < 86400: return f"{sec // 3600}h ago"
    if sec < 2592000: return f"{sec // 86400}d ago"
    return f"{sec // 2592000}mo ago"

def repo_data(item, token):
    repo = item["repo"]
    info = api_get(f"/repos/{repo}", token)
    commits = api_get(f"/repos/{repo}/commits?per_page=1", token)
    updated = commits[0]["commit"]["committer"]["date"] if commits else info.get("pushed_at")
    return {
        "mode": "repository",
        "repo": repo,
        "url": info["html_url"],
        "status": item.get("status", "Active"),
        "focus": item.get("focus", "Current development"),
        "description": shorten(info.get("description") or "No repository description"),
        "language": item.get("stack") or info.get("language") or "Mixed",
        "stars": info.get("stargazers_count", 0),
        "issues": search(f"repo:{repo} is:issue is:open", token)["total_count"],
        "prs": search(f"repo:{repo} is:pr is:open", token)["total_count"],
        "updated": ago(updated),
    }

def contributor_data(item, token):
    repo, user = item["repo"], item["contributor"]
    info = api_get(f"/repos/{repo}", token)
    merged = search(f"repo:{repo} is:pr author:{user} is:merged", token)["total_count"]
    opened = search(f"repo:{repo} is:pr author:{user} is:open", token)["total_count"]
    recent = search(f"repo:{repo} is:pr author:{user}", token, "updated", "desc", 1)
    latest = None
    if recent.get("items"):
        number = recent["items"][0]["number"]
        pr = api_get(f"/repos/{repo}/pulls/{number}", token)
        latest = {
            "number": number,
            "title": shorten(pr["title"], 62),
            "url": pr["html_url"],
            "state": "Merged" if pr.get("merged_at") else ("Open" if pr["state"] == "open" else "Closed"),
            "updated": ago(pr["updated_at"]),
        }
    return {
        "mode": "contributor",
        "repo": repo,
        "url": info["html_url"],
        "status": item.get("status", "Active Contributor"),
        "focus": item.get("focus", "Contributing via pull requests"),
        "contributor": user,
        "merged": merged,
        "open": opened,
        "latest": latest,
    }

def demo_repo(item):
    return {
        "mode":"repository","repo":item["repo"],"url":f"https://github.com/{item['repo']}",
        "status":"Active","focus":"Current development",
        "description":"Desktop software and developer tooling.",
        "language":item.get("stack") or "C++","stars":18,"issues":4,"prs":1,"updated":"1d ago"
    }

def demo_contributor(item):
    return {
        "mode":"contributor","repo":item["repo"],"url":f"https://github.com/{item['repo']}",
        "status":"Active Contributor","focus":"Contributing via pull requests","contributor":"qiyi71w",
        "merged":77,"open":0,
        "latest":{"number":364,"title":"docs(github): add optional Logs field to the bug form",
                  "url":"https://github.com/wimi321/lizzieyzy-next/pull/364",
                  "state":"Merged","updated":"8h ago"}
    }

def render_repo(d, y):
    return f'''
<a href="{esc(d["url"])}" target="_blank">
<rect class="card" x="20" y="{y}" rx="14" width="820" height="132"/>
<circle class="green" cx="46" cy="{y+28}" r="6"/>
<text class="repo" x="62" y="{y+34}">{esc(d["repo"])}</text>
<text class="status" x="810" y="{y+34}" text-anchor="end">{esc(d["status"])}</text>
<text class="focus" x="42" y="{y+66}">{esc(d["focus"])}</text>
<text class="desc" x="42" y="{y+91}">{esc(d["description"])}</text>
<text class="meta" x="42" y="{y+116}">{esc(d["language"])} · ★ {d["stars"]} · Issues {d["issues"]} · PRs {d["prs"]}</text>
<text class="meta" x="810" y="{y+116}" text-anchor="end">updated {esc(d["updated"])}</text>
</a>'''

def render_contributor(d, y):
    p = d.get("latest")
    if p:
        line = f'#{p["number"]}  {p["title"]}'
        url = p["url"]
        meta = f'{p["state"]} · {p["updated"]}'
    else:
        line, url, meta = "No pull request found", d["url"], ""
    return f'''
<a href="{esc(d["url"])}" target="_blank">
<rect class="card" x="20" y="{y}" rx="14" width="820" height="178"/>
<circle class="green" cx="46" cy="{y+28}" r="6"/>
<text class="repo" x="62" y="{y+34}">{esc(d["repo"])}</text>
<text class="status" x="810" y="{y+34}" text-anchor="end">{esc(d["status"])}</text>
<text class="focus" x="42" y="{y+65}">{esc(d["focus"])}</text>
<text class="meta" x="42" y="{y+88}">@{esc(d["contributor"])} · {d["merged"]} merged PRs · {d["open"]} open PRs</text>
</a>
<a href="{esc(url)}" target="_blank">
<rect class="latest" x="42" y="{y+105}" rx="9" width="776" height="58"/>
<text class="latest-label" x="58" y="{y+126}">LATEST PR</text>
<text class="latest-title" x="58" y="{y+150}">{esc(line)}</text>
<text class="meta" x="802" y="{y+150}" text-anchor="end">{esc(meta)}</text>
</a>'''

def svg(config, cards):
    y, chunks = 8, []
    for d in cards:
        if d["mode"] == "contributor":
            chunks.append(render_contributor(d, y)); y += 192
        else:
            chunks.append(render_repo(d, y)); y += 146
    height = y + 10
    body = "".join(chunks)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="860" height="{height}" viewBox="0 0 860 {height}">
<style>
.card{{fill:#f6f8fa;stroke:#d0d7de;stroke-width:1}} .latest{{fill:#fff;stroke:#d8dee4;stroke-width:1}}
.repo{{fill:#0969da;font:600 16px Arial,sans-serif}}
.status{{fill:#656d76;font:600 12px Arial,sans-serif}} .focus{{fill:#1f2328;font:600 14px Arial,sans-serif}}
.desc{{fill:#656d76;font:400 12px Arial,sans-serif}} .meta{{fill:#656d76;font:400 11px Consolas,monospace}}
.latest-label{{fill:#656d76;font:700 9px Arial,sans-serif;letter-spacing:.12em}}
.latest-title{{fill:#1f2328;font:600 12px Arial,sans-serif}} .green{{fill:#2da44e}}
</style>
<rect width="100%" height="100%" fill="#fff"/>
{body}
</svg>'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="profile.json")
    ap.add_argument("--output", default="assets/current-work.svg")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text())
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    cards = []
    for item in config["repos"]:
        mode = item.get("mode", "repository")
        if args.demo:
            cards.append(demo_contributor(item) if mode == "contributor" else demo_repo(item))
        else:
            cards.append(contributor_data(item, token) if mode == "contributor" else repo_data(item, token))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg(config, cards), encoding="utf-8")

if __name__ == "__main__":
    main()
