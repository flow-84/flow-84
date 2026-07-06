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


# Per Browser-Canvas gemessene Glyphenbreiten fuer '700 11px DejaVu Sans Bold'
# (breitester gaengiger Linux-Fallback -> auf schmaleren Fonts wie Verdana bleibt
# nur etwas mehr Rand, nie ein Ueberlauf). Unbekannte Zeichen: grosszuegiger Default.
GLYPH_W = {"0": 7.65, "1": 7.65, "2": 7.65, "3": 7.65, "4": 7.65, "5": 7.65,
           "6": 7.65, "7": 7.65, "8": 7.65, "9": 7.65, ".": 4.18, "-": 4.57,
           " ": 3.83, "P": 8.06, "R": 8.47, "O": 9.35, "F": 7.51, "I": 4.09,
           "L": 7.01, "A": 8.51, "U": 8.93, "E": 7.51}


def text_width(s, default=9.4):
    return sum(GLYPH_W.get(c, default) for c in s)


def build_svg(total_views):
    """Kompaktes Flat-Square-Badge (Stil komarev): dunkles Label links, Magenta-
    Zahl rechts, automatische Breite -> Zahl sitzt buendig, kein leerer Raum.
    Text je Segment zentriert, damit unterschiedliche Betrachter-Fonts nicht
    ins Nachbarsegment ueberlaufen."""
    label = "PROFIL-AUFRUFE"
    value = fmt(total_views)
    H, FS, PAD = 20, 11, 11
    lw = round(text_width(label) + 2 * PAD)
    rw = round(text_width(value) + 2 * PAD)
    W = lw + rw
    ty = 14  # Baseline vertikal zentriert
    lcx, rcx = lw / 2.0, lw + rw / 2.0  # Segment-Mittelpunkte
    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" role="img" aria-label="Profilaufrufe: %s">'
             % (W, H, W, H, value))
    p.append('<title>Profilaufrufe: %s</title>' % value)
    # Abgerundete Segmente (Hintergruende via Clip). Eindeutige Clip-ID, damit
    # mehrere Badges im selben Dokument sich nicht gegenseitig ueberklippen.
    cid = "rnd%d" % W
    p.append('<clipPath id="%s"><rect width="%d" height="%d" rx="4"/></clipPath>' % (cid, W, H))
    p.append('<g clip-path="url(#%s)">' % cid)
    p.append('<rect width="%d" height="%d" fill="%s"/>' % (lw, H, BG))
    p.append('<rect x="%d" width="%d" height="%d" fill="%s"/>' % (lw, rw, H, MAGENTA))
    p.append('</g>')
    # Feiner Neon-Rahmen
    p.append('<rect x="0.5" y="0.5" width="%d" height="%d" rx="4" fill="none" '
             'stroke="%s" stroke-opacity="0.5"/>' % (W - 1, H - 1, BORDER))
    # Texte (zentriert) mit leichtem Schatten fuer Lesbarkeit
    p.append('<g font-family="Verdana,DejaVu Sans,Segoe UI,sans-serif" '
             'font-size="%d" font-weight="700" text-anchor="middle">' % FS)
    p.append('<text x="%.1f" y="%d" fill="#000" fill-opacity="0.3">%s</text>' % (lcx, ty + 1, label))
    p.append('<text x="%.1f" y="%d" fill="%s">%s</text>' % (lcx, ty, CYAN, label))
    p.append('<text x="%.1f" y="%d" fill="#000" fill-opacity="0.3">%s</text>' % (rcx, ty + 1, value))
    p.append('<text x="%.1f" y="%d" fill="#ffffff">%s</text>' % (rcx, ty, value))
    p.append('</g>')
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

    svg = build_svg(total_views)
    _, svg_sha = get_json_file(repo, SVG_PATH, token)  # nur sha holen (kein JSON noetig)
    put_file(repo, SVG_PATH, token, svg.encode(),
             "Update assets/profile-views.svg [skip ci]", sha=svg_sha)

    print("profile-views: %d Aufrufe gesamt (%d Tage), 14T: %d/%d"
          % (total_views, len(daily), count_14d, uniques_14d))


if __name__ == "__main__":
    main()
