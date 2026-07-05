#!/usr/bin/env python3
"""Erzeugt assets/profile-views.svg (Profilaufrufe-Zaehler) selbst-gehostet.

Datenquelle: GitHub-Traffic-API des Profil-Repos (/traffic/views) liefert die
Tagesaufrufe der letzten 14 Tage. Diese werden pro Datum in
.github/data/profile-views.json akkumuliert (jeder Tag ist in der API autoritativ
-> kein Doppelzaehlen bei taeglichem Lauf), aufsummiert und als Neon-SVG
gerendert. Unabhaengig von jedem Fremddienst (Ersatz fuer komarev.com/ghpvc),
daher zuverlaessig sichtbar.
"""
import base64
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"
STATE_PATH = ".github/data/profile-views.json"
SVG_PATH = "assets/profile-views.svg"

BG = "#0a0118"
CYAN = "#00f0ff"
MAGENTA = "#ff00e5"
BORDER = "#b400ff"
DIM = "#b9a7d6"


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


def get_json_file(repo, path, token):
    """Liest eine JSON-Datei via Contents-API. Rueckgabe (daten, sha) oder (None, None)."""
    try:
        cur = api("/repos/%s/contents/%s?ref=main" % (repo, path), token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise
    raw = base64.b64decode(cur["content"]).decode()
    try:
        return json.loads(raw), cur.get("sha")
    except ValueError:
        return None, cur.get("sha")


def put_file(repo, path, token, content_bytes, message, sha=None):
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    api("/repos/%s/contents/%s" % (repo, path), token, method="PUT", data=payload)


def merge_daily(state, views):
    """Fuegt die API-Tageswerte in das gespeicherte daily-Map ein (autoritativ pro Datum)."""
    daily = dict(state.get("daily", {})) if state else {}
    for v in views:
        day = v.get("timestamp", "")[:10]
        if not day:
            continue
        daily[day] = {"count": int(v.get("count", 0)), "uniques": int(v.get("uniques", 0))}
    return daily


def fmt(n):
    """Tausender-Trennung mit Punkt (deutsch): 12345 -> '12.345'."""
    return "{:,}".format(int(n)).replace(",", ".")


def build_svg(total_views, count_14d, uniques_14d):
    W, H = 320, 34
    big = fmt(total_views)
    sub = "14 T: %s · %s eindeutig" % (fmt(count_14d), fmt(uniques_14d))
    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" role="img" aria-label="Profilaufrufe: %s">'
             % (W, H, W, H, big))
    p.append('<rect x="0.5" y="0.5" width="%d" height="%d" rx="8" fill="%s" '
             'stroke="%s" stroke-opacity="0.55"/>' % (W - 1, H - 1, BG, BORDER))
    # Auge-Icon
    p.append('<g transform="translate(14,17)" fill="none" stroke="%s" stroke-width="1.6">' % MAGENTA)
    p.append('<path d="M-7 0 C-4 -5 4 -5 7 0 C4 5 -4 5 -7 0 Z"/>')
    p.append('<circle cx="0" cy="0" r="2" fill="%s" stroke="none"/>' % MAGENTA)
    p.append('</g>')
    # Label
    p.append('<text x="30" y="21" font-family="Segoe UI,Helvetica,Arial,sans-serif" '
             'font-size="11" font-weight="700" letter-spacing="0.5" fill="%s">PROFIL-AUFRUFE</text>'
             % MAGENTA)
    # Grosse Zahl (rechtsbuendig)
    p.append('<text x="%d" y="15" text-anchor="end" font-family="Segoe UI,Helvetica,Arial,sans-serif" '
             'font-size="15" font-weight="700" fill="%s">%s</text>' % (W - 12, CYAN, big))
    # Sub-Zeile (rechtsbuendig)
    p.append('<text x="%d" y="27" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" '
             'font-size="8.5" fill="%s">%s</text>' % (W - 12, DIM, sub))
    p.append('</svg>')
    return "\n".join(p)


def main():
    token = os.environ["GH_TOKEN"]
    repo = os.environ.get("GITHUB_REPOSITORY", "flow-84/flow-84")

    traffic = api("/repos/%s/traffic/views" % repo, token)
    views = traffic.get("views", [])
    count_14d = int(traffic.get("count", 0))
    uniques_14d = int(traffic.get("uniques", 0))

    state, state_sha = get_json_file(repo, STATE_PATH, token)
    daily = merge_daily(state, views)
    total_views = sum(d.get("count", 0) for d in daily.values())

    new_state = {"daily": daily, "total_views": total_views}
    put_file(repo, STATE_PATH, token,
             (json.dumps(new_state, indent=2, sort_keys=True) + "\n").encode(),
             "Update profile-views state [skip ci]", sha=state_sha)

    svg = build_svg(total_views, count_14d, uniques_14d)
    _, svg_sha = get_json_file(repo, SVG_PATH, token)  # nur sha holen (kein JSON noetig)
    put_file(repo, SVG_PATH, token, svg.encode(),
             "Update assets/profile-views.svg [skip ci]", sha=svg_sha)

    print("profile-views: %d Aufrufe gesamt (%d Tage), 14T: %d/%d"
          % (total_views, len(daily), count_14d, uniques_14d))


if __name__ == "__main__":
    main()
