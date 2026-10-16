#!/usr/bin/env python3
"""Build omaboot.live: the public site of OmaBoot? Live. Static, no JavaScript, Python stdlib only.

Usage: site_build.py [--releases FILE] [--out DIR]
       site_build.py --serve [PORT] [--out DIR]

The build reads data/site.json (addresses), data/releases.json (published releases, newest
first, each with its "edition"; [] until the first one), data/editions.json (Live, Omarchy, Lab),
data/tests.json (the criteria and how OmaBoot? Live tests each one, for Docs), data/allowed_signers
(the release keys) and pages/*.html (the copy: each page is an HTML fragment whose first lines are
<!-- title: ... --> and <!-- description: ... -->), and writes dist/: one directory per page, one
per test under docs/, 404.html, site.css, assets/ (screens drawn by boot-live's tools/screens,
the editions' startup-disk icons, JetBrains Mono), favicon.svg, allowed_signers, robots.txt,
sitemap.xml, _headers and _redirects for Cloudflare Pages. Boot and the OmaBoot? wordmark are
drawn here as inline SVG from the prototype's pixels.

Tokens in pages: {{BOOT}} {{BOOT pleased}} (Boot's sprite), {{WORDMARK}}, {{DIO}} (a link to
DoesItOmarchy.com), {{EDITIONS}} (the editions, with each one's newest release), {{AREAS}} (the
test areas as tiles), {{DOCS}} (the list of tests), {{SIGNERS}} (the keys), {{FP_RELEASE}},
{{ISO}} (the newest ISO's file name), {{SOURCE}}, {{IMAGE_REPO}}, {{CONTACT ...}}.
<!-- TODO(owner): ... --> comments are listed on every build and left out of dist/.

After writing, the build checks dist/: every internal link resolves, and no token, TODO or
example address is left. It exits non-zero if not.

--serve previews dist/ on 127.0.0.1 (default port 8091) the way Cloudflare Pages serves it:
directory indexes, 404.html, _redirects and the headers in _headers (including the CSP).
"""
import base64
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")
# GitHub's mark (Octicons mark-github), shown beside the repository link in the bar.
OCTOCAT = ("M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94"
           "-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07"
           "-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0"
           " 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25"
           ".54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z")

# Navigation order; the slug is the URL path and the pages/ file name ("index" is /).
NAV = [("download", "Download"), ("docs", "Docs")]
DOCS_GUIDES = [("write", "Write the stick", "Any USB stick of 4 GB or more, from macOS, Linux or Windows. Then hold Option."),
               ("verify", "Verify a download", "Check the checksum and the signature before you write the stick."),
               ("privacy", "What gets sent", "What a report holds, where it goes, and what boot.watch keeps (nothing).")]
FOOTER_ONLY = ["write", "verify", "privacy"]  # the guides: in Docs and the footer, so the top line fits a phone
WIDE = {"index", "download", "docs"}  # pages that lay out their own width; the others read as prose

# ── Palette (boot-wip/boot-live-proto.src.html, "OmaBoot?") ─────────────────────────────────
# Boot's own colours stay the same in both themes: he's a character, not text.
PIX = {"c": "#4fa6ad", "C": "#8fe3e8", "k": "#0b0d10", "W": "#eef2f4", "y": "#c98f3a", "Y": "#ffd479"}


# ── Boot: the prototype's v16 sprite, 16×12 pixels ──────────────────────────────────────────
def boot_rows(face="neutral", blink=False):
    body = ".ckkkkkkkkkkkkc."
    r = [list(body) for _ in range(5)]  # rows 4–8: eyes and mouth
    L, R, M = 4, 9, 6
    if blink:
        for p in (L, R):
            for i in range(3):
                r[1][p + i] = "C"
    elif face == "pleased":
        for p in (L, R):
            r[1][p], r[0][p + 1], r[1][p + 2] = "W", "W", "W"
    else:
        for p in (L, R):
            for i in range(3):
                r[0][p + i] = r[1][p + i] = "W"
    if face == "pleased":
        r[3][M], r[4][M + 1], r[4][M + 2], r[3][M + 3] = "C", "C", "C", "C"
    else:
        r[3][M + 1] = r[3][M + 2] = "C"
    return [".......yy.......", "........c.......", "..cccccccccccc..", body,
            *("".join(x) for x in r), body, "..cccccccccccc..", "....cc....cc...."]


def pixel_paths(rows, colours, skip=".", offset=(0, 0)):
    """One <path> per colour, horizontal runs merged: crisp pixel art at any size."""
    runs = {}
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            ch = row[x]
            if ch == skip or ch not in colours:
                x += 1
                continue
            n = 1
            while x + n < len(row) and row[x + n] == ch:
                n += 1
            runs.setdefault(ch, []).append(f"M{x + offset[0]} {y + offset[1]}h{n}v1h-{n}z")
            x += n
    return "".join(f'<path fill="{colours[ch]}" d="{"".join(d)}"/>' for ch, d in runs.items())


def boot_svg(face="neutral", cls="boot", label="Boot"):
    """Boot with an idle life: CSS blinks his eyes and his antenna tip (none with reduced motion)."""
    base = boot_rows(face)
    shut = boot_rows(face, blink=True)
    # Closed eyes: only the pixels that change when he blinks, shown over the base for a beat.
    lids = ["".join(b if a != b else "." for a, b in zip(o, s)) for o, s in zip(base, shut)]
    tip = [".......YY......."]
    aria = f'role="img" aria-label="{html.escape(label)}"' if label else 'aria-hidden="true"'
    return (f'<svg class="{cls}" viewBox="0 0 16 12" shape-rendering="crispEdges" {aria}>'
            f'{pixel_paths(base, PIX)}<g class="lids">{pixel_paths(lids, PIX)}</g>'
            f'<g class="tip">{pixel_paths(tip, PIX)}</g></svg>')


# ── The wordmark: the prototype's 5×7 letters ───────────────────────────────────────────────
BIG = {
    "O": [".111.", "1...1", "1...1", "1...1", "1...1", "1...1", ".111."],
    "m": [".....", ".....", "11.1.", "1.1.1", "1.1.1", "1.1.1", "1.1.1"],
    "a": [".....", ".....", ".111.", "....1", ".1111", "1...1", ".1111"],
    "B": ["1111.", "1...1", "1...1", "1111.", "1...1", "1...1", "1111."],
    "o": [".....", ".....", ".111.", "1...1", "1...1", "1...1", ".111."],
    "t": [".1...", ".1...", "1111.", ".1...", ".1...", ".1..1", "..11."],
    "?": [".111.", "1...1", "....1", "...1.", "..1..", ".....", "..1.."],
    "L": ["1....", "1....", "1....", "1....", "1....", "1....", "11111"],
    "i": ["..1..", ".....", ".11..", "..1..", "..1..", "..1..", ".111."],
    "v": [".....", ".....", "1...1", "1...1", "1...1", ".1.1.", "..1.."],
    "e": [".....", ".....", ".111.", "1...1", "11111", "1....", ".111."],
}


def wordmark_svg(word="OmaBoot? Live", cls="wordmark", label="OmaBoot? Live"):
    """Letters in the text colour, the question mark in violet (the accent)."""
    rows, x = [""] * 7, 0
    for ch in word:
        if ch == " ":
            rows = [r + "..." for r in rows]
            continue
        mark = "q" if ch == "?" else "1"
        rows = [r + g.replace("1", mark) + "." for r, g in zip(rows, BIG[ch])]
    w = len(rows[0]) - 1
    paths = pixel_paths(rows, {"1": "currentColor", "q": "var(--accent)"})
    paths = paths.replace('fill="var(--accent)"', 'class="q"')
    aria = f'role="img" aria-label="{html.escape(label)}"' if label else 'aria-hidden="true"'
    return f'<svg class="{cls}" viewBox="0 0 {w} 7" shape-rendering="crispEdges" {aria}>{paths}</svg>'


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -2 16 16" shape-rendering="crispEdges">'
           + pixel_paths(boot_rows(), PIX) + "</svg>\n")


# ── Releases ────────────────────────────────────────────────────────────────────────────────
RELEASE_FIELDS = ("version", "date", "omarchy", "iso", "size", "sha256", "sha256sums", "signature",
                  "packages", "difference", "build_log")


def load_releases(path):
    rels = json.load(open(path))
    if not isinstance(rels, list):
        sys.exit(f"{path}: expected a list of releases (newest first)")
    for r in rels:
        missing = [k for k in RELEASE_FIELDS if not r.get(k)]
        if missing:
            sys.exit(f"{path}: release {r.get('version', '?')} lacks {', '.join(missing)}")
        for k in ("iso", "sha256sums", "signature", "packages", "difference", "build_log"):
            if not r[k].startswith("https://"):
                sys.exit(f"{path}: {r['version']} {k} must be an https:// address")
        if not re.fullmatch(r"[0-9a-f]{64}", r["sha256"]):
            sys.exit(f"{path}: {r['version']} sha256 must be 64 lowercase hex digits")
        datetime.date.fromisoformat(r["date"])
        if r.get("edition", "live") not in ("live", "omarchy", "lab"):
            sys.exit(f"{path}: {r['version']} edition must be live, omarchy or lab")
    return rels


def gb(n):
    return f"{n / 1e9:.1f} GB"


def load_editions():
    eds = json.load(open(os.path.join(DATA, "editions.json")))
    for e in eds:
        if not os.path.exists(os.path.join(HERE, "assets", "editions", e["id"] + ".png")):
            sys.exit(f"data/editions.json: no icon assets/editions/{e['id']}.png")
    return eds


def newest(rels, edition):
    return next((r for r in rels if r.get("edition", "live") == edition), None)


def edition_card(e, r, full):
    """One edition as a card: its startup-disk icon, what it is, and its newest release or when."""
    main = " main" if e.get("main") else ""
    head = (f'<img class="disk" src="/assets/editions/{e["id"]}.png" width="64" height="64" alt="">'
            f'<div><p class="role">{html.escape(e["role"])}</p><h3>{html.escape(e["name"])}</h3></div>')
    if r:
        name = r["iso"].rsplit("/", 1)[1]
        get = (f'<p class="get"><a class="button" href="{html.escape(r["iso"])}">Download {html.escape(r["version"])}</a>'
               f'<span class="quiet">{gb(r["size"])} · {html.escape(r["date"])}</span></p>')
        if full:
            a = lambda k, t: f'<a href="{html.escape(r[k])}">{t}</a>'
            notes = f'<p>{html.escape(r["notes"])}</p>' if r.get("notes") else ""
            get += f'''{notes}<p class="fine">Built from Omarchy {html.escape(r["omarchy"])} · <code>{html.escape(name)}</code></p>
<p class="tag">SHA256</p><pre><code>{r["sha256"]}</code></pre>
<ul class="files"><li>{a("sha256sums", "SHA256SUMS")}</li><li>{a("signature", "SHA256SUMS.sig")}</li><li><a href="/allowed_signers">allowed_signers</a></li>
<li>{a("packages", "Package list")}</li><li>{a("difference", "Difference report")}</li><li>{a("build_log", "Build log")}</li></ul>'''
    else:
        get = f'<p class="get"><span class="status">{html.escape(e["status"])}</span><span class="quiet">{html.escape(e["size"])}</span></p>'
    return f'<article class="edition ed-{e["id"]}{main}"><div class="ed-head">{head}</div><p>{html.escape(e["line"])}</p>{get}</article>'


def editions_html(rels, full=False):
    eds = load_editions()
    cards = "".join(edition_card(e, newest(rels, e["id"]), full) for e in eds)
    return f'<div class="editions">{cards}</div>'


# ── Docs: the tests ─────────────────────────────────────────────────────────────────────────
LEVEL = {"high": (3, "High confidence"), "medium": (2, "Medium confidence"), "low": (1, "Low confidence"),
         "none": (0, "Not tested live")}
KIND = {"pass": "Could pass when it shouldn't", "fail": "Could fail when it shouldn't", "none": "Could end without a verdict"}


def load_tests():
    t = json.load(open(os.path.join(DATA, "tests.json")))
    for c in t["criteria"]:
        c["slug"] = c["id"].replace(".", "-")
    return t


def area_slug(name):
    return re.sub(r"[^a-z]+", "-", name.lower()).strip("-")


def meter(level, words=True):
    """How sure a test is: the home page's square, filled as far as the test is sure."""
    label = LEVEL[level][1]
    text = f'<span>{label}</span>' if words else ""
    return f'<span class="meter m-{level}" title="{label}"><i class="sq q-{level}" aria-hidden="true"></i>{text}</span>'


def squares(cs):
    """A tile's row of squares: one per criterion, filled as far as the test is sure."""
    out = []
    for c in cs:
        for _ in range(2 if c.get("also") else 1):
            out.append(f'<i class="sq q-{c["confidence"]}"></i>')
    return f'<span class="squares" aria-hidden="true">{"".join(out)}</span>'


def areas_html(t):
    tiles = []
    for a in t["areas"]:
        cs = [c for c in t["criteria"] if c["area"] == a["name"]]
        n = sum(2 if c.get("also") else 1 for c in cs)
        live = sum((2 if c.get("also") else 1) for c in cs if c["confidence"] != "none")
        tiles.append(f'<a class="area-tile" href="/docs/#{area_slug(a["name"])}"><h3>{html.escape(a["name"])}</h3>'
                     f'{squares(cs)}<p>{live} of {n} tested live</p></a>')
    return f'<div class="area-tiles">{"".join(tiles)}</div>'


def docs_html(t):
    out = []
    for a in t["areas"]:
        cs = [c for c in t["criteria"] if c["area"] == a["name"]]
        rows = "".join(
            f'<li><a class="test-row" href="/docs/{c["slug"]}/"><span class="tt">{html.escape(c["title"])}</span>'
            f'<code>{html.escape(c["id"])}</code><span class="how">{html.escape(c["method"])}</span>{meter(c["confidence"], False)}</a></li>'
            for c in cs)
        note = f'<p class="quiet">{html.escape(a["note"])}</p>' if a["note"] else ""
        out.append(f'<section class="docs-area" id="{area_slug(a["name"])}"><h2>{html.escape(a["name"])}</h2>{note}<ul class="tests">{rows}</ul></section>')
    return "".join(out)


def test_body(t, c):
    cs = t["criteria"]
    i = cs.index(c)
    prev, nxt = (cs[i - 1] if i else None), (cs[i + 1] if i + 1 < len(cs) else None)
    ids = html.escape(c["id"]) + (f' · {html.escape(c["also"])}' if c.get("also") else "")
    blk = lambda h, body: f'<section class="blk"><h2>{h}</h2>{body}</section>' if body else ""
    p = lambda s: f"<p>{html.escape(s)}</p>" if s else ""
    hw = "".join(f"<li>{html.escape(x)}</li>" for x in c["hardware"])
    pits = "".join(f'<li><span class="kind k-{f["kind"]}">{KIND[f["kind"]]}</span><span>{html.escape(f["text"])}</span></li>' for f in c["pitfalls"])
    pager = '<nav class="pager" aria-label="Tests">' + (
        f'<a href="/docs/{prev["slug"]}/">← {html.escape(prev["title"])}</a>' if prev else "<span></span>") + (
        f'<a href="/docs/{nxt["slug"]}/">{html.escape(nxt["title"])} →</a>' if nxt else "<span></span>") + "</nav>"
    return f'''<p class="crumbs"><a href="/docs/">Docs</a> / <a href="/docs/#{area_slug(c["area"])}">{html.escape(c["area"])}</a></p>
<h1>{html.escape(c["title"])}</h1>
<div class="test-meta"><code>{ids}</code><span class="how">{html.escape(c["method"])}</span>{meter(c["confidence"])}</div>
<div class="test-grid">
{blk("How it tests", p(c["tests"]))}
{blk("How it decides", p(c["decides"]))}
{blk("How sure it is", p(c["why"]))}
{blk("On a real Mac", f'<ul class="hw">{hw}</ul>' if hw else "")}
{blk("What could mislead it", f'<ul class="pits">{pits}</ul>' if pits else "")}
</div>
{pager}'''


# ── Keys ────────────────────────────────────────────────────────────────────────────────────
def signers():
    """(principal, options, key line, comment, fingerprint) for each key in data/allowed_signers."""
    out = []
    for line in open(os.path.join(DATA, "allowed_signers")):
        if not line.strip() or line.startswith("#"):
            continue
        principal, opts, kind, blob, comment = line.split()
        fp = base64.b64encode(hashlib.sha256(base64.b64decode(blob)).digest()).decode().rstrip("=")
        out.append((principal, opts, f"{kind} {blob}", comment, "SHA256:" + fp))
    return out


def signers_html():
    roles = {"omaboot-release": "Release key. Signs every release; each signature needs the maintainer's approval.",
             "omaboot-release-backup": "Backup key. Kept offline, on paper. It signs only a release that ships a new key list, if the release key is ever lost or compromised."}
    items = "".join(f'<li><p>{roles.get(c, c)}</p><p class="fp"><code>{fp}</code></p></li>' for _, _, _, c, fp in signers())
    return f'<ul class="keys">{items}</ul>'


# ── Pages ───────────────────────────────────────────────────────────────────────────────────
def link(url, text):
    return f'<a href="{html.escape(url)}">{text}</a>' if url else text


def fill(body, cfg, rels, todos, slug, tests):
    for t in re.findall(r"<!--\s*TODO\(owner\):(.*?)-->", body, re.S):
        todos.append(f"pages/{slug}.html: {' '.join(t.split())}")
    body = re.sub(r"\s*<!--\s*TODO\(owner\):.*?-->", "", body, flags=re.S)
    iso = rels[0]["iso"].rsplit("/", 1)[1] if rels else "omaboot-live-<version>.iso"
    rep = {
        "{{BOOT}}": boot_svg(label=""), "{{BOOT pleased}}": boot_svg("pleased", label=""),
        "{{WORDMARK}}": wordmark_svg(cls="wordmark big"),
        "{{DIO}}": f'<a href="{cfg["doesitomarchy"]}">DoesItOmarchy.com</a>',
        "{{OMARCHY}}": f'<a href="{cfg["omarchy"]}">omarchy.org</a>',
        "{{EDITIONS}}": editions_html(rels), "{{EDITIONS full}}": editions_html(rels, full=True),
        "{{METER high}}": meter("high"), "{{METER medium}}": meter("medium"), "{{METER none}}": meter("none"),
        "{{DOWNLOAD_SAY}}": f'<div class="say">{boot_svg("pleased", label="")}<p>fresh build. check it before you write it.</p></div>' if rels
                             else f'<div class="say">{boot_svg(label="")}<p>not out yet. I\'m still being tested on real Macs.</p></div>',
        "{{AREAS}}": areas_html(tests), "{{DOCS}}": docs_html(tests), "{{SIGNERS}}": signers_html(),
        "{{FP_RELEASE}}": signers()[0][4], "{{ISO}}": html.escape(iso),
        "{{SOURCE}}": link(cfg["source"], "the source code") + ("" if cfg["source"] else " (published on GitHub with the first release)"),
        "{{IMAGE_REPO}}": link(cfg["image_repo"], "the image's build repository"),
    }
    for k, v in rep.items():
        body = body.replace(k, v)
    # {{CONTACT text}}: the sentence only when there's somewhere to write to.
    body = re.sub(r"\{\{CONTACT (.*?)\}\}", lambda m: m.group(1).replace("[", f'<a href="{html.escape(cfg["contact"])}">').replace("]", "</a>")
                  if cfg["contact"] else "", body)
    return body


def read_page(slug):
    src = open(os.path.join(PAGES, slug + ".html")).read()
    title = re.search(r"<!--\s*title:\s*(.*?)\s*-->", src).group(1)
    desc = re.search(r"<!--\s*description:\s*(.*?)\s*-->", src).group(1)
    body = re.sub(r"<!--\s*(title|description):.*?-->\n?", "", src)
    return title, desc, body


def document(cfg, slug, title, desc, body):
    path = "/" if slug == "index" else f"/{slug}/"
    section = "docs" if slug.startswith("docs/") or slug in [g for g, _, _ in DOCS_GUIDES] else slug
    nav = "".join(f'<a href="/{s}/"{" aria-current=\"page\"" if s == section else ""}>{t}</a>' for s, t in NAV)
    nav += (f'<a class="repo" href="{cfg["repo"]}" rel="noopener">'
            f'<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="{OCTOCAT}"/></svg>{cfg["repo"].rsplit("/", 1)[1]}</a>')
    if slug not in WIDE:
        body = f'<div class="prose">{body.strip()}</div>'
    cls = "page-" + slug.replace("/", "-") + (" page-test" if slug.startswith("docs/") else "")
    full_title = cfg["name"] if slug == "index" else f"{title} · {cfg['name']}"
    url = cfg["site"] + path
    source = f' · {link(cfg["source"], "Source")}' if cfg["source"] else ""
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/site.css">
<meta name="color-scheme" content="dark">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{cfg["name"]}">
<meta property="og:title" content="{html.escape(full_title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
</head>
<body class="{cls}">
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="bar">
  <a class="brand" href="/">{boot_svg(cls="boot mini", label="")}{wordmark_svg(label="OmaBoot? Live, home")}</a>
  <nav aria-label="Site">{nav}</nav>
</div></header>
<main id="main">
{body.strip()}
</main>
<footer class="site"><div class="bar">
  <p>OmaBoot? Live is made by <a href="{cfg["doesitomarchy"]}">DoesItOmarchy.com</a>. <strong>A community site. Not officially affiliated with <a href="https://omarchy.org" rel="noopener">Omarchy</a> or the <a href="https://omarchy.org/foundation/" rel="noopener">Omacom Foundation</a>.</strong></p>
  <p><a href="/write/">Write the stick</a> · <a href="/verify/">Verify</a> · <a href="/privacy/">Privacy</a> · <a href="https://status.boot.watch">boot.watch status</a>{source}</p>
  <p>No cookies, no analytics, no third-party scripts.</p>
</div></footer>
</body>
</html>
'''


# ── Output ──────────────────────────────────────────────────────────────────────────────────
HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Cross-Origin-Opener-Policy: same-origin
  Content-Security-Policy: default-src 'none'; script-src 'none'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'

/site.css
  Cache-Control: public, max-age=3600

/assets/*
  Cache-Control: public, max-age=86400

/allowed_signers
  Content-Type: text/plain; charset=utf-8
  Cache-Control: public, max-age=300
"""


def build(out, releases_file):
    cfg = json.load(open(os.path.join(DATA, "site.json")))
    rels = load_releases(releases_file)
    todos = [f"data/site.json: {k[:-5]}: {v}" for k, v in cfg.items() if k.endswith("_TODO") and not cfg[k[:-5]]]
    assert os.path.basename(out) and os.path.abspath(out) not in (HERE, "/", os.path.expanduser("~"))
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    tests = load_tests()
    slugs = ["index"] + [s for s, _ in NAV] + FOOTER_ONLY
    pages = [(slug, *read_page(slug)) for slug in slugs + ["404"]]
    for c in tests["criteria"]:
        pages.append((f"docs/{c['slug']}", c["title"], f"How OmaBoot? Live tests {c['title'].lower()} ({c['id']}) on an Intel Mac, how it decides, and how sure it is.", test_body(tests, c)))
    for slug, title, desc, body in pages:
        doc = document(cfg, slug, title, desc, fill(body, cfg, rels, todos, slug, tests))
        target = os.path.join(out, "404.html") if slug == "404" else os.path.join(out, "" if slug == "index" else slug, "index.html")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, "w").write(doc)
    slugs += [f"docs/{c['slug']}" for c in tests["criteria"]]
    shutil.copy2(os.path.join(HERE, "site.css"), os.path.join(out, "site.css"))
    shutil.copytree(os.path.join(HERE, "assets"), os.path.join(out, "assets"))
    shutil.copy2(os.path.join(DATA, "allowed_signers"), os.path.join(out, "allowed_signers"))
    open(os.path.join(out, "favicon.svg"), "w").write(FAVICON)
    open(os.path.join(out, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {cfg['site']}/sitemap.xml\n")
    open(os.path.join(out, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{cfg['site']}{'/' if s == 'index' else f'/{s}/'}</loc></url>\n" for s in slugs) + "</urlset>\n")
    redirects = ["# Generated by site_build.py. Domain redirects (doesitboot.com, omaboot.com, boot.watch) are Cloudflare rules, not here."]
    if rels:  # a stable address for the newest image and its checksums
        redirects += [f"/latest.iso {rels[0]['iso']} 302", f"/SHA256SUMS {rels[0]['sha256sums']} 302",
                      f"/SHA256SUMS.sig {rels[0]['signature']} 302"]
    open(os.path.join(out, "_redirects"), "w").write("\n".join(redirects) + "\n")
    open(os.path.join(out, "_headers"), "w").write(HEADERS)
    problems = check(out)
    print(f"site -> {out}: {len(slugs)} pages, {len(rels)} release(s)", file=sys.stderr)
    if todos:
        print(f"\n{len(todos)} owner TODO(s):", file=sys.stderr)
        for t in todos:
            print("  - " + t, file=sys.stderr)
    if problems:
        print("\nCHECK FAILED:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        sys.exit(1)


def check(out):
    """Internal links resolve; no leftover tokens, TODOs or example addresses in what ships."""
    problems = []
    for root, _, files in os.walk(out):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            doc = open(path).read()
            rel = os.path.relpath(path, out)
            for bad in ("{{", "}}", "TODO", "example.com", "lorem"):
                if bad in doc:
                    problems.append(f"{rel}: contains {bad!r}")
            for href in re.findall(r'(?:href|src)="([^"]+)"', doc):
                if href.startswith(("https://", "#", "mailto:")):
                    continue
                if not href.startswith("/"):
                    problems.append(f"{rel}: relative or insecure link {href}")
                    continue
                p = href.split("#")[0].lstrip("/")
                target = os.path.join(out, p, "index.html") if (p == "" or p.endswith("/")) else os.path.join(out, p)
                if not os.path.exists(target):
                    problems.append(f"{rel}: broken link {href}")
            for frag in re.findall(r'href="#([^"]+)"', doc):
                if f'id="{frag}"' not in doc:
                    problems.append(f"{rel}: missing anchor #{frag}")
    return problems


def serve(out, port):
    import fnmatch
    import http.server

    def read(name):
        p = os.path.join(out, name)
        return open(p).read() if os.path.exists(p) else ""

    rules, cur = [], None
    for line in read("_headers").splitlines():
        if line and not line[0].isspace():
            cur = (line.strip(), [])
            rules.append(cur)
        elif line.strip() and cur:
            k, v = line.strip().split(":", 1)
            cur[1].append((k.strip(), v.strip()))
    redirects = {a: (b, int(c)) for a, b, c in (l.split() for l in read("_redirects").splitlines()
                                                 if l.strip() and not l.startswith("#"))}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=out, **k)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in redirects:
                self.send_response(redirects[path][1])
                self.send_header("Location", redirects[path][0])
                self.end_headers()
                return
            if not os.path.exists(self.translate_path(path)):
                body = open(os.path.join(out, "404.html"), "rb").read()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def guess_type(self, path):
            return "text/plain; charset=utf-8" if path.endswith("allowed_signers") else super().guess_type(path)

        def end_headers(self):
            path = self.path.split("?")[0]
            for pattern, hs in rules:
                if pattern == path or ("*" in pattern and fnmatch.fnmatch(path, pattern)):
                    for k, v in hs:
                        if k.lower() != "content-type":
                            self.send_header(k, v)
            super().end_headers()

    print(f"serving {out} at http://127.0.0.1:{port}/ (Ctrl+C stops)", file=sys.stderr)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main(argv):
    out = os.path.abspath(argv[argv.index("--out") + 1]) if "--out" in argv else os.path.join(HERE, "dist")
    if "--serve" in argv:
        i = argv.index("--serve")
        port = int(argv[i + 1]) if len(argv) > i + 1 and argv[i + 1].isdigit() else 8091
        return serve(out, port)
    releases = argv[argv.index("--releases") + 1] if "--releases" in argv else os.path.join(DATA, "releases.json")
    build(out, releases)


if __name__ == "__main__":
    main(sys.argv[1:])
