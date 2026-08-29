#!/usr/bin/env python3
"""Erzeugt assets/activity-chart.svg: ein Balkendiagramm der taeglichen Beitraege
der letzten 31 Tage, aus der GitHub GraphQL contributionCalendar-API. Laeuft mit
dem eigenen METRICS_TOKEN im eigenen Workflow, daher kein geteiltes Rate-Limit
wie bei externen Diensten (z.B. github-readme-activity-graph).
"""
import base64
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"
GRAPHQL = API + "/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
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


def graphql(token, login):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        payload = json.loads(r.read().decode())
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"]))
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def last_31_days(calendar):
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    days.sort(key=lambda d: d[0])
    return days[-31:]


def build_svg(days):
    W, H = 760, 220
    pad_l, pad_r, pad_t, pad_b = 16, 16, 44, 30
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(days) or 1
    counts = [c for _, c in days]
    peak = max(counts) if counts else 0
    total = sum(counts)
    gap = 3
    bar_w = (chart_w - gap * (n - 1)) / n if n else chart_w

    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
              'role="img" aria-label="Aktivitaetsverlauf">' % (W, H, W, H))
    p.append('<rect x="0.5" y="0.5" width="%d" height="%d" rx="14" fill="#0a0118" '
              'stroke="#b400ff" stroke-opacity="0.45"/>' % (W - 1, H - 1))
    p.append('<text x="%d" y="26" font-family="Segoe UI,Helvetica,Arial,sans-serif" '
              'font-size="16" font-weight="700" fill="#ff00e5">Beitraege der letzten 31 Tage</text>' % pad_l)
    p.append('<text x="%d" y="26" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" '
              'font-size="13" fill="#00f0ff">%d Beitraege</text>' % (W - pad_r, total))

    p.append('<defs><linearGradient id="bar" x1="0" y1="0" x2="0" y2="1">'
              '<stop offset="0%" stop-color="#00f0ff"/>'
              '<stop offset="100%" stop-color="#b400ff"/></linearGradient></defs>')

    base_y = pad_t + chart_h
    p.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#b400ff" stroke-opacity="0.3"/>'
              % (pad_l, base_y, W - pad_r, base_y))

    x = float(pad_l)
    for date, count in days:
        h = (count / peak * (chart_h - 4)) if peak else 0.0
        y = base_y - h
        if count:
            p.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="1.5" fill="url(#bar)">'
                      '<title>%s: %d</title></rect>' % (x, y, bar_w, max(h, 2), date, count))
        else:
            p.append('<rect x="%.2f" y="%.2f" width="%.2f" height="2" rx="1" fill="#2a1f4d">'
                      '<title>%s: 0</title></rect>' % (x, base_y - 2, bar_w, date))
        x += bar_w + gap

    if days:
        p.append('<text x="%d" y="%d" font-family="Segoe UI,Arial,sans-serif" font-size="11" '
                  'fill="#b9a7d6">%s</text>' % (pad_l, H - 8, days[0][0]))
        p.append('<text x="%d" y="%d" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" '
                  'font-size="11" fill="#b9a7d6">%s</text>' % (W - pad_r, H - 8, days[-1][0]))

    p.append('</svg>')
    return "\n".join(p)


def commit(token, repo, svg):
    sha = None
    try:
        req = urllib.request.Request(API + "/repos/%s/contents/assets/activity-chart.svg?ref=main" % repo)
        req.add_header("Authorization", "Bearer " + token)
        req.add_header("Accept", "application/vnd.github+json")
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read().decode()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    payload = {
        "message": "Update assets/activity-chart.svg [skip ci]",
        "content": base64.b64encode(svg.encode()).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    body = json.dumps(payload).encode()
    req = urllib.request.Request(API + "/repos/%s/contents/assets/activity-chart.svg" % repo,
                                  data=body, method="PUT")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req):
        pass


def main():
    token = os.environ["GH_TOKEN"]
    repo = os.environ.get("GITHUB_REPOSITORY", "flow-84/flow-84")
    login = os.environ.get("GITHUB_REPOSITORY_OWNER", "flow-84")
    calendar = graphql(token, login)
    days = last_31_days(calendar)
    svg = build_svg(days)
    commit(token, repo, svg)
    print("activity-chart.svg: %d Tage, %d Beitraege gesamt" % (len(days), sum(c for _, c in days)))


if __name__ == "__main__":
    main()
