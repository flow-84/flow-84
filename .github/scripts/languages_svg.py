#!/usr/bin/env python3
"""Erzeugt assets/languages.svg aus den echten Sprach-Bytes ALLER eigenen Repos
(inkl. privat) via GitHub-API und committet es. Unabhaengig von der Commit-Email-
Zuordnung (im Gegensatz zu lowlighter/metrics), daher zuverlaessig befuellt.
"""
import base64
import html
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"

# Linguist-Farben fuer gaengige Sprachen; Unbekannte fallen auf die Neon-Palette zurueck.
COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c", "Shell": "#89e051",
    "HCL": "#844FBA", "Dockerfile": "#384d54", "Vue": "#41b883", "Svelte": "#ff3e00",
    "Astro": "#ff5a03", "Java": "#b07219", "Go": "#00ADD8", "Ruby": "#701516",
    "PHP": "#4F5D95", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
    "Kotlin": "#A97BFF", "Rust": "#dea584", "Jupyter Notebook": "#DA5B0B",
    "Makefile": "#427819", "PowerShell": "#012456", "Solidity": "#AA6746",
    "Nix": "#7e7eff", "Lua": "#000080", "MDX": "#fcb32c", "Batchfile": "#C1F12E",
    "Handlebars": "#f7931e", "PLpgSQL": "#336790", "Roff": "#ecdebe",
}
NEON = ["#00f0ff", "#b400ff", "#ff00e5", "#7a1d8c", "#00b3bd"]


def api(path, token, method="GET", data=None):
    url = path if path.startswith("http") else API + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def fetch_totals(token):
    repos, page = [], 1
    while True:
        batch = api("/user/repos?per_page=100&affiliation=owner&sort=pushed&page=%d" % page, token)
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    totals = {}
    used = 0
    for r in repos:
        if r.get("fork"):
            continue
        try:
            langs = api("/repos/%s/languages" % r["full_name"], token)
        except Exception:
            continue
        used += 1
        for k, v in langs.items():
            totals[k] = totals.get(k, 0) + v
    return totals, used, len(repos)


def rank(totals, limit=8):
    total = sum(totals.values())
    items = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    top = items[:limit]
    out = []
    for i, (name, val) in enumerate(top):
        pct = (val / total * 100.0) if total else 0.0
        out.append((name, pct, COLORS.get(name, NEON[i % len(NEON)])))
    shown = sum(v for _, v in top)
    if total and shown < total:
        out.append(("Other", (total - shown) / total * 100.0, "#6b7280"))
    return out, total


def build_svg(langs, total):
    W, pad, bar_y, bar_h = 480, 16, 42, 14
    bar_w = W - 2 * pad
    rows = (len(langs) + 1) // 2 if langs else 1
    legend_top = bar_y + bar_h + 22
    row_h = 24
    H = legend_top + rows * row_h + 6
    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
             'role="img" aria-label="Meistgenutzte Sprachen">' % (W, H, W, H))
    p.append('<rect x="0.5" y="0.5" width="%d" height="%d" rx="14" fill="#0a0118" '
             'stroke="#b400ff" stroke-opacity="0.45"/>' % (W - 1, H - 1))
    p.append('<text x="%d" y="28" font-family="Segoe UI,Helvetica,Arial,sans-serif" '
             'font-size="16" font-weight="700" fill="#ff00e5">Meistgenutzte Sprachen</text>' % pad)
    if total and langs:
        p.append('<clipPath id="clip"><rect x="%d" y="%d" width="%d" height="%d" rx="7"/></clipPath>'
                 % (pad, bar_y, bar_w, bar_h))
        p.append('<g clip-path="url(#clip)">')
        x = float(pad)
        for _, pct, color in langs:
            w = bar_w * pct / 100.0
            p.append('<rect x="%.2f" y="%d" width="%.2f" height="%d" fill="%s"/>'
                     % (x, bar_y, w + 0.6, bar_h, color))
            x += w
        p.append('</g>')
    else:
        p.append('<text x="%d" y="%d" font-family="Segoe UI,Arial,sans-serif" font-size="13" '
                 'fill="#00f0ff">Keine Sprachdaten gefunden</text>' % (pad, bar_y + 12))
    col_w = (W - 2 * pad) / 2.0
    for i, (name, pct, color) in enumerate(langs):
        cx = pad + (i % 2) * col_w + 6
        cy = legend_top + (i // 2) * row_h
        p.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s"/>' % (cx, cy - 4, color))
        p.append('<text x="%.1f" y="%.1f" font-family="Segoe UI,Arial,sans-serif" font-size="13" '
                 'fill="#00f0ff"><tspan font-weight="600">%s</tspan> '
                 '<tspan fill="#b9a7d6">%.1f%%</tspan></text>'
                 % (cx + 12, cy, html.escape(name, quote=True), pct))
    p.append('</svg>')
    return "\n".join(p)


def commit(token, repo, svg):
    sha = None
    try:
        cur = api("/repos/%s/contents/assets/languages.svg?ref=main" % repo, token)
        sha = cur.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    payload = {
        "message": "Update assets/languages.svg (API-Sprachaggregation) [skip ci]",
        "content": base64.b64encode(svg.encode()).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    api("/repos/%s/contents/assets/languages.svg" % repo, token, method="PUT", data=payload)


def main():
    token = os.environ["GH_TOKEN"]
    repo = os.environ.get("GITHUB_REPOSITORY", "flow-84/flow-84")
    totals, used, n = fetch_totals(token)
    langs, total = rank(totals)
    svg = build_svg(langs, total)
    commit(token, repo, svg)
    print("languages.svg: %d Sprachen aus %d/%d Repos, %d Bytes gesamt"
          % (len(langs), used, n, total))


if __name__ == "__main__":
    main()
