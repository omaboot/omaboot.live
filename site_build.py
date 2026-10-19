#!/usr/bin/env python3
"""Build omaboot.live: the public site of OmaBoot? Live. Static, Python stdlib only. One small
script of our own, copy.js, adds copy buttons to the commands; the pages work without it.

Usage: site_build.py [--releases FILE] [--reports DIR] [--out DIR]
       site_build.py --serve [PORT] [--out DIR]

The build reads data/site.json (addresses), data/releases.json (published releases, newest
first, each with its "edition"; [] until the first one), data/editions.json (Live, Omarchy, Lab),
data/tests.json (the criteria and how OmaBoot? Live tests each one, for Docs), data/fixes.json (the
OmaBoot? fixes, copied from DoesItOmarchy.com by tools/sync_fixes.py) and data/fixes-detail.json (what
this site adds about each, for /fixes/), data/allowed_signers
(the release keys) and pages/*.html (the copy: each page is an HTML fragment whose first lines are
<!-- title: ... --> and <!-- description: ... -->), and writes dist/: one directory per page, one
per test under docs/, 404.html, site.css, assets/ (screens drawn by boot-live's tools/screens,
the editions' startup-disk icons, the fonts), copy.js, favicon.svg, allowed_signers, robots.txt,
sitemap.xml, _headers and _redirects for Cloudflare Pages. Boot and the OmaBoot? wordmark are
drawn here as inline SVG (Boot from the prototype's pixels, the wordmark from data/wordmark.json),
and the home page's iMac drawing is data/hero-imac.svg (tools/hero_drawing.py).

Tokens in pages: {{BOOT}} {{BOOT pleased}} (Boot's sprite), {{WORDMARK}}, {{DIO}} (a link to
DoesItOmarchy.com), {{EDITIONS}} (the editions, with each one's newest release), {{AREAS}} (the
test areas as tiles), {{DOCS}} (the list of tests), {{FIXES}} (the fixes), {{SIGNERS}} (the keys), {{FP_RELEASE}},
{{ISO}} (the newest ISO's file name), {{SOURCE}}, {{IMAGE_REPO}}, {{CONTACT ...}}, {{HERO_ART}} (the
iMac drawing), {{VERIFIED}} (what the newest release was checked for), {{TEST_MEDIA}} (the test file
and the test disc, from data/test-media.json).
<!-- TODO(owner): ... --> comments are listed on every build and left out of dist/.

After writing, the build checks dist/: every internal link resolves, and no token, TODO or
example address is left. It exits non-zero if not.

--serve previews dist/ on 127.0.0.1 (default port 8091) the way Cloudflare Pages serves it:
directory indexes, 404.html, _redirects and the headers in _headers (including the CSP).
"""
import base64
import datetime
import fnmatch
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
NAV = [("download", "Download"), ("verify", "Verify"), ("fixes", "Fixes"), ("docs", "Docs")]
GUIDES = ["write", "privacy"]  # in Docs and the footer, not the bar; they count as Docs there
FOOTER_ONLY = GUIDES
SUBPAGES = {"docs/console": "console"}  # slug -> its pages/ file: pages that live under /docs/ but aren't tests
WIDE = {"index", "download", "docs", "docs/console", "fixes"}  # pages that lay out their own width; the others read as prose

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


# ── The wordmark: BigBlue Terminal 437's letters as outlines (owner's pick C3, 2026-10-16) ───
def wordmark_svg(cls="wordmark", label="OmaBoot? Live"):
    """Letters in the text colour, the question mark in violet (the accent). The outlines are made
    once by tools/wordmark.py (data/wordmark.json), in the font's pixels: 9 tall."""
    wm = json.load(open(os.path.join(DATA, "wordmark.json")))
    aria = f'role="img" aria-label="{html.escape(label)}"' if label else 'aria-hidden="true"'
    return (f'<svg class="{cls}" viewBox="{wm["x"]:g} {wm["y"]:g} {wm["width"]:g} {wm["height"]:g}" shape-rendering="crispEdges" {aria}>'
            f'<path fill="currentColor" d="{wm["letters"]}"/><path class="q" d="{wm["q"]}"/></svg>')


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -2 16 16" shape-rendering="crispEdges">'
           + pixel_paths(boot_rows(), PIX) + "</svg>\n")


# ── Releases ────────────────────────────────────────────────────────────────────────────────
RELEASE_FIELDS = ("version", "date", "omarchy", "iso", "size", "sha256", "sha256sums", "signature",
                  "packages", "difference", "build_log")


def load_releases(path, reports):
    """The releases, newest first; each gets its "report" (data/reports/<version>.json, made by
    tools/release_report.py from the release's own files) when there is one."""
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
        rp = os.path.join(reports, f"{r['version']}.json")
        if os.path.exists(rp):
            r["report"] = json.load(open(rp))
    return rels


def report_url(r):
    """Where a release's difference report reads best: its page here, else the published file."""
    return f'/releases/{r["version"]}/' if r.get("report") else r["difference"]


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


def edition_card(e, r, full, earlier=""):
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
<p class="tag">SHA256</p><pre class="wrap" data-label="the SHA256"><code>{r["sha256"]}</code></pre>
<ul class="files"><li>{a("sha256sums", "SHA256SUMS")}</li><li>{a("signature", "SHA256SUMS.sig")}</li><li><a href="/allowed_signers">allowed_signers</a></li>
<li>{a("packages", "Package list")}</li><li><a href="{html.escape(report_url(r))}">Difference report</a></li><li>{a("build_log", "Build log")}</li></ul>
{earlier}'''
    else:
        get = f'<p class="get"><span class="status">{html.escape(e["status"])}</span><span class="quiet">{html.escape(e["size"])}</span></p>'
    sup = f' <sup>{html.escape(e["sup"])}</sup>' if e.get("sup") else ""
    return (f'<article class="edition ed-{e["id"]}{main}"><div class="ed-top"><div class="ed-head">{head}</div>'
            f'<p>{html.escape(e["line"])}{sup}</p></div><div class="ed-get">{get}</div></article>')


def earlier_html(rels, edition):
    """The edition's older releases, newest first, as plain links to each one's image."""
    old = [r for r in rels if r.get("edition", "live") == edition][1:]
    if not old:
        return ""
    links = " / ".join(f'<a href="{html.escape(r["iso"])}">{html.escape(r["version"])}</a>' for r in old)
    return f'<p class="earlier"><span class="tag">Earlier</span> {links}</p>'


# What a release's difference report found: the Download page's Verify section and each release's
# page. Without a report (before the first release) the tiles say what each check is.
def report_tiles(c):
    return [f'<li><b>{c["official_files"]:,}</b><span>of {c["packages"]:,} packages: the official ISO\'s own file, the same SHA-256</span></li>',
            f'<li><b>{c["added"]:,}</b><span>package{"" if c["added"] == 1 else "s"} added to the live system, each with why</span></li>',
            f'<li><b>{c["unexplained"]:,}</b><span>unexplained, of {c["files_differing"]:,} files that differ</span></li>']


def verified_html(rels):
    r = newest(rels, "live")
    c = (r or {}).get("report", {}).get("counts")
    tiles = []
    if c:
        tiles += report_tiles(c)
    else:
        tiles += ['<li><b>SHA-256</b><span>every package: the official ISO\'s own file, or an addition listed with why</span></li>',
                  '<li><b>0</b><span>unexplained differences: a release ships only when every file that differs is explained</span></li>']
    tiles += ['<li><b>ED25519</b><span>the checksums are signed; the key never touches the build machine</span></li>',
              '<li><b>Public</b><span>built by GitHub Actions from a tagged commit; the build log is linked</span></li>']
    report = (f'<a href="{html.escape(report_url(r))}">The full difference report for {html.escape(r["version"])}</a>'
              if r else "Each release links its full difference report")
    return (f'<ul class="vtiles">{"".join(tiles)}</ul>'
            f'<p class="method"><b>How:</b> each release is built from Omarchy\'s own ISO build at a named commit, '
            f'then compared with the official ISO of the same release, package by package and file by file. '
            f'Every difference needs a rule that explains it.</p>'
            f'<p class="method-links">{report} / <a href="/verify/">Verify your download</a></p>')


# The test media (boot-live's tools/testfile and tools/testcd): optional, any stick, card, drive or
# disc does for the tests; these also prove the bytes came back right. They don't change with each
# release, so they have one place: data/test-media.json's "base" on get.omaboot.live, with their
# SHA256SUMS, its signature ("signed": once the owner has signed it) and allowed_signers.
# "available": false while they're off get.omaboot.live (owner, 2026-10-18: until the first release,
# re-signed with the new release keys): the cards stay, their downloads say TBA.
def load_test_media():
    path = os.path.join(DATA, "test-media.json")
    tm = json.load(open(path))
    if not str(tm.get("base", "")).startswith("https://") or not tm["base"].endswith("/") or not isinstance(tm.get("signed"), bool) \
            or not isinstance(tm.get("available", True), bool):
        sys.exit(f"{path}: base must be an https:// address ending in /, signed and available true or false")
    for k in ("file", "disc"):
        m = tm.get(k) or {}
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(m.get("name", ""))) or not isinstance(m.get("size"), int) \
                or not re.fullmatch(r"[0-9a-f]{64}", str(m.get("sha256", ""))):
            sys.exit(f"{path}: {k} needs a file name, a size in bytes and a sha256")
    return tm


ICON_FILE = ('<svg class="media-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2.8h8.2L18.5 7v14.2H6z"/><path d="M14 2.8V7h4.5"/>'
             '<path d="M8.7 11h2M12.3 11h3M8.7 14h3.6M14 14h1.3M8.7 17h1.3M11.6 17h3.7"/></svg>')
ICON_DISC = ('<svg class="media-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.2"/><circle cx="12" cy="12" r="2.4"/>'
             '<path d="M12 5.6a6.4 6.4 0 0 1 6.4 6.4"/></svg>')


def test_media_html():
    tm = load_test_media()
    base = html.escape(tm["base"])

    def get(k):
        m = tm[k]
        if not tm.get("available", True):
            return f'<p class="get"><span class="button ghost tba" aria-disabled="true">{m["name"]}: {FP_TBA}</span></p>'
        return (f'<p class="get"><a class="button ghost" href="{base}{m["name"]}">Download {m["name"]}</a>'
                f'<span class="quiet">{m["size"] / 1e6:.1f} MB</span></p>'
                f'<p class="tag">SHA256</p><pre class="wrap" data-label="the SHA256 of {m["name"]}"><code>{m["sha256"]}</code></pre>')
    sums = f'<a href="{base}SHA256SUMS"><code>SHA256SUMS</code></a>'
    check = (f'Their checksums are in {sums}, signed with the release keys (<a href="{base}SHA256SUMS.sig"><code>SHA256SUMS.sig</code></a>): '
             f'<a href="/verify/">check them</a> as you would the image.' if tm["signed"] else f'Their checksums are in {sums}.')
    if not tm.get("available", True):
        check = 'Both come with the first release, with their checksums signed with the release keys.'
    return f'''<div class="media">
<article class="media-card">{ICON_FILE}<div>
<p class="role">USB · SD card · FireWire</p><h3>Test file</h3>
<p>Copy <code>OMABOOT-TEST.BIN</code> to the top folder of a stick, card or drive you already have. Nothing gets erased.</p>
<ul class="media-points">
<li>A port test finds it and checks every byte. Nothing is written to the drive.</li>
<li>It reads FAT and exFAT (most sticks and cards) and Mac OS Extended. On APFS or NTFS the tests still run, without the byte check.</li>
<li>Keep the file's name.</li>
</ul>
{get("file")}</div></article>
<article class="media-card">{ICON_DISC}<div>
<p class="role">Optical drive</p><h3>Test disc</h3>
<p>Burn <code>omaboot-test.iso</code> to a CD-R as a disc image. Any CD or DVD works for the test; this one proves the drive read it right.</p>
<div class="os-rows">
<div class="os-row"><p class="os">macOS</p><pre data-label="burning on macOS"><code>hdiutil burn omaboot-test.iso</code></pre></div>
<div class="os-row"><p class="os">Linux</p><pre data-label="burning on Linux"><code>xorriso -as cdrecord -v dev=/dev/sr0 omaboot-test.iso</code></pre></div>
<div class="os-row"><p class="os">Windows</p><p class="os-say">Right-click the file, <b>Burn disc image</b>.</p></div>
</div>
{get("disc")}</div></article>
</div>
<p class="method-links">{check}</p>'''


def editions_html(rels, full=False):
    eds = load_editions()
    cards = "".join(edition_card(e, newest(rels, e["id"]), full, earlier_html(rels, e["id"]) if full else "") for e in eds)
    # what every edition shares, as full-width rows under the cards (owner, 2026-10-16). The report
    # link goes to the newest release's difference report; before the first release, to what's checked.
    live = newest(rels, "live")
    report = report_url(live) if live else "/download/#verified"
    # (site.css lays the cards out as a table: tops, then each card's download part, then these rows
    # across all three)
    rows = "".join(f'<p class="ed-all ed-all-{i}"><span class="check" aria-hidden="true">✓</span><b>{t}</b></p>' for i, t in enumerate((
        f'Verifiable <a href="{html.escape(report)}">difference report</a> from the <a href="https://github.com/omacom/omarchy-iso">official Omarchy ISO</a>',
        "Tests your Intel Mac for Omarchy compatibility, with full hardware checks"), 1))
    return f'<div class="editions">{cards}{rows}</div>'


# ── A release's page: its difference report ─────────────────────────────────────────────────
CATEGORY = {"unexplained": ("Unexplained", "No rule accounts for it. A release with any doesn't ship."),
            "ours": ("Ours", "An OmaBoot? change: the tester, patched modules, the boot menu, splash and settings."),
            "generated": ("Generated at build time", "Written while the image is built, from the installed packages: caches, indexes, keyrings, the initramfs."),
            "package": ("Files of a package we add", "The files the added packages install.")}
AREA = {"iso": "ISO 9660", "esp": "EFI partition", "rootfs": "root file system"}


def release_body(r, rels, cfg, fixes):
    rep = r["report"]
    c = rep["counts"]
    eds = {e["id"]: e["name"] for e in load_editions()}
    name = f'{eds.get(r.get("edition", "live"), "OmaBoot?")} {r["version"]}'
    e = html.escape
    oi = rep["official_iso"]
    gh = cfg["image_repo"]
    rel_page = f'{gh}/releases/tag/{rep["tag"]}' if gh else ""
    commit = lambda repo, sha: f'<a href="{repo}/commit/{sha}"><code>{sha[:7]}</code></a>' if repo and sha else (f"<code>{sha[:7]}</code>" if sha else "")
    facts = [("Official ISO", f'<a href="{e(oi["url"])}">{e(oi["url"].rsplit("/", 1)[-1])}</a> <span class="quiet">SHA-256</span> <code class="hash">{e(oi["sha256"])}</code>'),
             ("Its signature", e(oi["signature"])),
             ("omarchy-iso", f'{commit("https://github.com/omacom/omarchy-iso", oi["omarchy_iso_commit"])} <span class="quiet">the official build we start from</span>'),
             ("Our changes", f'{commit(gh, rep["fork_commit"])} <span class="quiet">on top of it, as readable commits</span>'),
             ("Packages", f'pinned to the Arch Linux Archive of {e(rep["arch_archive_date"])}, Omarchy\'s stable channel and t2linux'),
             ("Tester", f'{e(rep["boot_live"]["version"])}'),
             ("Built", f'{e(rep["built_at"].replace("T", " ").replace("Z", " UTC"))}' + (f' · <a href="{e(rep["build_run"])}">build log</a>' if rep["build_run"] else ""))]
    facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts if v)
    changes = "".join(f'<tr><td><code>{e(p["name"])}</code></td><td>{e(p["change"])}</td><td><code>{e(p["version"])}</code></td>'
                      f'<td>{"the official ISO\'s own file" if p["official_file"] else e(p["repo"]) + " (not on the official ISO)"}</td><td>{e(p["why"])}</td></tr>'
                      for p in rep["package_changes"])
    groups = []
    for cat in ("unexplained", "ours", "generated", "package"):
        gs = [g for g in rep["groups"] if g["category"] == cat]
        title, what = CATEGORY[cat]
        n = sum(g["count"] for g in gs)
        if not gs:
            groups.append(f'<section class="dgroup" id="{cat}"><h3>{title} <span class="n">0</span></h3><p class="quiet">{what}</p><p>None.</p></section>')
            continue
        items = []
        for g in gs:
            files = "".join(f'<li><span class="area">{AREA.get(a, a)}</span><code>{e(p)}</code><span class="d">{e(d)}</span></li>' for a, p, d in g["files"])
            body = f'<ul class="paths">{files}</ul>' if files else '<p class="quiet">Too many to list here: every path is in <code>diff-report.tsv.gz</code>.</p>'
            fx = [f for f in fixes["fixes"] if any(fnmatch.fnmatch(p, pat) for _, p, _ in g["files"] for pat in f["detail"]["files"])]
            fx = f' <span class="fix-refs">({", ".join(fix_link(f) for f in fx)})</span>' if fx else ""
            items.append(f'<details><summary><span class="cnt">{g["count"]:,}</span>{e(g["explanation"])}{fx}</summary>{body}</details>')
        groups.append(f'<section class="dgroup" id="{cat}"><h3>{title} <span class="n">{n:,}</span></h3><p class="quiet">{what}</p>{"".join(items)}</section>')
    same = [x for x in rels if x.get("edition", "live") == r.get("edition", "live")]
    i = same.index(r)
    newer, older = (same[i - 1] if i else None), (same[i + 1] if i + 1 < len(same) else None)
    link_to = lambda x, label: (f'<a href="{e(report_url(x))}">{label}</a>' if x else "<span></span>")
    pager = f'<nav class="pager" aria-label="Releases">{link_to(older, f"← {e(older['version'])}" if older else "")}{link_to(newer, f"{e(newer['version'])} →" if newer else "")}</nav>'
    originals = [f'<a href="{e(r["difference"])}">diff-report (signed with the release)</a>', f'<a href="{e(r["packages"])}">packages.tsv</a>',
                 f'<a href="{e(r["sha256sums"])}">SHA256SUMS</a>', f'<a href="{e(r["signature"])}">SHA256SUMS.sig</a>']
    if rel_page:
        originals.append(f'<a href="{e(rel_page)}">the GitHub release</a>')
    return f'''<p class="crumbs"><a href="/download/">Download</a> / Releases / {e(r["version"])}</p>
<h1>{e(name)}: difference report</h1>
<p class="lede">Compared with the official Omarchy {e(rep["omarchy"])} ISO, package by package and file by file. Every difference has a rule that explains it.</p>
<ul class="vtiles">{"".join(report_tiles(c))}</ul>
<h2 id="built">What it's built from</h2>
<dl class="facts-list">{facts_html}</dl>
<h2 id="packages">Packages that differ from the official live system</h2>
<div class="table-scroll"><table class="pkgs"><thead><tr><th>Package</th><th>Change</th><th>Version</th><th>File</th><th>Why</th></tr></thead><tbody>{changes}</tbody></table></div>
<p class="quiet">Every other package is the same version as on the official ISO. {c["official_files"]:,} of the {c["packages"]:,} packages are the official ISO's very files (same SHA-256), checked one by one in <code>packages.tsv</code>.</p>
<h2 id="files">Files that differ: {c["files_differing"]:,}</h2>
<p class="quiet">Across the ISO 9660 volume, the EFI partition and the root file system. Compared: type, permissions, owner, size, content (SHA-256) and link targets; timestamps are ignored. Open a group to see its files.</p>
{"".join(groups)}
<h2 id="originals">The original files</h2>
<p>This page is made from the files published with the release, all listed in its signed <code>SHA256SUMS</code>: {" / ".join(originals)}.</p>
{pager}'''


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


def level_chip(levels, key, main=False):
    return f'<span class="lvl{" main" if main else ""}" title="{html.escape(levels[key]["means"])}">{html.escape(levels[key]["name"])}</span>'


# ── Fixes: the registry's copy (data/fixes.json) and this site's detail (data/fixes-detail.json) ──
def load_fixes():
    reg = json.load(open(os.path.join(DATA, "fixes.json")))
    detail = json.load(open(os.path.join(DATA, "fixes-detail.json")))
    ids = [f["id"] for f in reg["fixes"]]
    missing = [i for i in ids if i not in detail]
    extra = [i for i in detail if not i.startswith("_") and i not in ids]
    if missing or extra:
        sys.exit("data/fixes-detail.json: " + "; ".join(
            ([f"no entry for {', '.join(missing)} (new in the registry: write one)"] if missing else [])
            + ([f"{', '.join(extra)} not in data/fixes.json (gone from the registry, or not synced)"] if extra else [])))
    for f in reg["fixes"]:
        f.update(detail=detail[f["id"]])
    return reg


def fix_link(f):
    return f'<a href="/fixes/#{html.escape(f["id"])}">{html.escape(f["name"])}</a>'


def fixes_for(fixes, ids):
    """The fixes that can change any of these criteria."""
    return [f for f in fixes["fixes"] if set(f.get("criteria", [])) & set(ids)]


def fixes_html(fixes, tests, cfg):
    """/fixes/: a tile per fix to jump to it, then each fix as a panel: the problem, what it changes
    and how it works side by side, and its facts in three groups (where it acts, what a run shows,
    where it comes from)."""
    e = html.escape
    titles = {c["id"]: (c["slug"], c["title"]) for c in tests["criteria"]}
    for c in tests["criteria"]:
        if c.get("also"):
            titles[c["also"]] = (c["slug"], c["title"])
    repo = cfg["image_repo"]
    cfgs = lambda ids: "<br>".join(f'<a href="{e(fixes["configs"][i]["url"])}">{e(fixes["configs"][i]["name"])} [{e(fixes["configs"][i]["identifier"])}]</a>' for i in ids)
    crit = lambda i: f'<a href="/docs/{titles[i][0]}/">{e(fixes["criteria"].get(i, titles[i][1]))}</a>' if i in titles else e(fixes["criteria"].get(i, i))
    levels = {lv["id"]: lv for lv in fixes["fix_levels"]}  # where a fix can live, from the registry (data/fixes.json)
    chips = lambda f: "".join(level_chip(levels, p["level"], i == 0) for i, p in enumerate(f["levels"]))
    tiles = "".join(f'<a class="fix-tile" href="#{e(f["id"])}"><span class="fix-num">{n:02d}</span><h2>{e(f["name"])}</h2><p>{e(f["detail"]["short"])}</p>'
                    f'<span class="lvls">{chips(f)}</span></a>'
                    for n, f in enumerate(fixes["fixes"], 1))
    out = [f'<nav class="fix-tiles" aria-label="The fixes">{tiles}</nav>']
    # the map: every level, top to bottom, with the fixes that live there
    rows = []
    for lv in fixes["fix_levels"]:
        key, name, means = lv["id"], lv["name"], lv["means"]
        here = [(n, f, i == 0) for n, f in enumerate(fixes["fixes"], 1) for i, p in enumerate(f["levels"]) if p["level"] == key]
        refs = "".join(f'<a class="lvl-ref{" main" if main else ""}" href="#{e(f["id"])}"><span class="fix-num">{n:02d}</span>{e(f["name"])}</a>' for n, f, main in here)
        empty = "never touched" if key == "firmware" else "none"
        rows.append(f'<li class="lvl-row{"" if here else " empty"}{" fw" if key == "firmware" else ""}"><span class="lvl-name">{name}</span>'
                    f'<span class="lvl-means">{e(means)}</span><span class="lvl-fixes">{refs or f'<span class="quiet">{empty}</span>'}</span></li>')
    out.append(f'<section class="lvl-map" id="levels"><h2>Where each fix lives</h2><p class="quiet">From what you see down to the firmware. '
               f'A fix that spans levels is listed at each; its main level is in violet.</p><ol class="lvl-rows">{"".join(rows)}</ol></section>')
    for n, f in enumerate(fixes["fixes"], 1):
        d = f["detail"]
        devices = ", ".join(f'<code>{e(x["id"])}</code>' + (f' subsystem <code>{e(x["subsystem"])}</code>' if x.get("subsystem") else "") for x in f.get("devices", []))
        upstream = "<br>".join(f'<a href="{e(u["url"])}" rel="noopener">{e(u["title"])}</a>' for u in f.get("upstream", []))
        if f.get("upstream_note"):
            upstream += ("<br>" if upstream else "") + e(f["upstream_note"])
        # a source item names its own repository ("repo": boot-live) when it isn't in the image's build repository
        source = "".join(f'<span class="src">' + (f'<code>{e(s["repo"])}: {e(s["path"])}</code>' if s.get("repo") else
                                                   f'<a href="{e(repo)}/blob/HEAD/{e(s["path"])}"><code>{e(s["path"])}</code></a>' if repo else f'<code>{e(s["path"])}</code>')
                         + f' {e(s["what"])}</span>' for s in d["source"])
        if not repo and any(not s.get("repo") for s in d["source"]):
            source += '<span class="quiet">In the image\'s build repository, published with the first release.</span>'
        groups = [("Where it acts", [("Hardware", e(f["hardware"])), ("Devices", devices), ("Configurations", cfgs(f.get("configs", []))),
                                     ("In OmaBoot? Live", e(d["applies"]))]),
                  ("What a run shows", [("How a run shows it", e(d["proof"])), ("Tests", e(d.get("tests", ""))),
                                        ("Results it can change", ", ".join(crit(i) for i in f.get("criteria", []))), ("Leaves alone", e(d["leaves"])),
                                        ("Tested on", cfgs(f.get("tested_on", [])))]),
                  ("Where it comes from", [("Since", f'OmaBoot? {e(f["since"])}'), ("Upstream", upstream), ("Source", source)])]
        facts = "".join(f'<section class="fix-group"><h3>{h}</h3><dl>{"".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows if v)}</dl></section>'
                        for h, rows in groups)
        how = "".join(f"<p>{e(x)}</p>" for x in d["detail"])
        out.append(f'<article class="fix" id="{e(f["id"])}">'
                   f'<header class="fix-head"><span class="fix-num">{n:02d}</span><h2>{e(f["name"])}</h2><code>{e(f["id"])}</code></header>'
                   f'<div class="fix-levels"><span class="fix-label">Lives in</span><ul>'
                   + "".join(f'<li>{level_chip(levels, p["level"], i == 0)}<span>{e(p["what"])}</span></li>' for i, p in enumerate(f["levels"])) + '</ul></div>'
                   f'<p class="fix-problem"><span class="fix-label">Without it</span>{e(d["problem"])}</p>'
                   f'<div class="fix-text"><section><h3>What it changes</h3><p>{e(f["changes"])}</p></section><section><h3>How it works</h3>{how}</section></div>'
                   f'<div class="fix-facts">{facts}</div>'
                   f'<p class="fix-out"><a href="{e(f["url"])}">This fix on DoesItOmarchy.com<span aria-hidden="true"> ↗</span></a></p></article>')
    return "".join(out)


def test_body(t, c, fixes):
    cs = t["criteria"]
    i = cs.index(c)
    prev, nxt = (cs[i - 1] if i else None), (cs[i + 1] if i + 1 < len(cs) else None)
    ids = html.escape(c["id"]) + (f' · {html.escape(c["also"])}' if c.get("also") else "")
    blk = lambda h, body: f'<section class="blk"><h2>{h}</h2>{body}</section>' if body else ""
    p = lambda s: f"<p>{html.escape(s)}</p>" if s else ""
    hw = "".join(f"<li>{html.escape(x)}</li>" for x in c["hardware"])
    fx = "".join(f'<li>{fix_link(f)}: {html.escape(f["detail"]["problem"])} A result it changes says <em>with OmaBoot? {html.escape(f["name"])}</em>.</li>'
                 for f in fixes_for(fixes, [c["id"]] + ([c["also"]] if c.get("also") else [])))
    pits = "".join(f'<li class="p-{f["kind"]}"><span class="kind k-{f["kind"]}">{KIND[f["kind"]]}</span><span>{html.escape(f["text"])}</span></li>' for f in c["pitfalls"])
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
{blk("OmaBoot? fixes", f'<ul class="hw">{fx}</ul>' if fx else "")}
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


FP_TBA = "TBA on first release"


def signers_html():
    """The keys as cards, one per row, release key first: an icon, its role, the fingerprint with
    a copy button (copy.js) (owner, 2026-10-18)."""
    key = '<circle cx="7.5" cy="12" r="3.6"/><path d="M11.1 12H21M17.5 12v3.2M20.3 12v2.4"/>'
    paper = ('<path d="M5.5 2.8h8.7l4.3 4.3v14.1h-13z"/><path d="M14.2 2.8v4.3h4.3"/>'
             '<circle cx="9.4" cy="14" r="2.3"/><path d="M11.7 14h4.6M15 14v2.1"/>')
    roles = {"omaboot-release": ("Release key", key, "Signs every release, each with the maintainer's approval."),
             "omaboot-release-backup": ("Backup key", paper, "Kept offline, on paper. Signs only a release that ships a new key list, if the release key is ever lost.")}
    # Until the first release the keys aren't published (owner, 2026-10-18): the cards say so.
    order = sorted(signers(), key=lambda k: k[3] != "omaboot-release") or [(None, None, None, c, None) for c in roles]
    cards = []
    for _, _, _, c, fp in order:
        name, icon, role = roles.get(c, (c, key, ""))
        shown = (f'<pre class="fp" data-copy="Copy the {name.lower()}\'s fingerprint"><code>{fp}</code></pre>' if fp
                 else f'<p class="fp-tba">Fingerprint: {FP_TBA}</p>')
        cards.append(f'<li class="key-card"><svg class="key-icon" viewBox="0 0 24 24" aria-hidden="true">{icon}</svg>'
                     f'<div><h3>{name}</h3><p>{role}</p>{shown}</div></li>')
    return f'<ul class="keys">{"".join(cards)}</ul>'


# ── Pages ───────────────────────────────────────────────────────────────────────────────────
def link(url, text):
    return f'<a href="{html.escape(url)}">{text}</a>' if url else text


def fill(body, cfg, rels, todos, slug, tests, fixes):
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
        "{{DOWNLOAD_SAY}}": f'<div class="say">{boot_svg("pleased", label="")}<p>fresh build. check it before you flash it.</p></div>' if rels
                             else f'<div class="say">{boot_svg(label="")}<p>not out yet. I\'m still being tested on real Macs.</p></div>',
        "{{HERO_ART}}": open(os.path.join(DATA, "hero-imac.svg")).read().strip(),
        "{{VERIFIED}}": verified_html(rels), "{{TEST_MEDIA}}": test_media_html(),
        "{{AREAS}}": areas_html(tests), "{{DOCS}}": docs_html(tests), "{{FIXES}}": fixes_html(fixes, tests, cfg), "{{SIGNERS}}": signers_html(),
        "{{FP_RELEASE}}": signers()[0][4] if signers() else FP_TBA, "{{ISO}}": html.escape(iso),
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


def asset_version(name):
    """A short hash of a file's content, added to its address (/site.css?v=…) so a browser that
    cached the old file fetches the new one on the next release instead of mixing the two."""
    return hashlib.sha256(open(os.path.join(HERE, name), "rb").read()).hexdigest()[:10]


# ── Docs index: a sidebar on every docs page (a disclosure on narrow screens) ───────────────
DOCS_GUIDES = [("/docs/", "Docs overview"), ("/write/", "Flash a USB stick"), ("/verify/", "Verify a download"),
               ("/docs/console/", "Console commands"), ("/docs/#bootwatch", "boot.watch"), ("/docs/#t2", "T2 Macs"),
               ("/privacy/", "What gets sent"), ("/docs/#faq", "FAQ")]


def page_toc(body):
    """The page's own sections, from its headings, for the top of the sidebar (long pages only)."""
    items = []
    for m in re.finditer(r'<section class="([^"]*)" id="([^"]+)">\s*<h2>(.*?)</h2>', body, re.S):
        if "docs-area" not in m.group(1):
            items.append((m.start(), m.group(2), re.sub(r"<[^>]+>", "", m.group(3)).split(":")[0], 0))
    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body, re.S):
        items.append((m.start(), m.group(1), re.sub(r"<[^>]+>", "", m.group(2)), 0))
    for m in re.finditer(r'<section class="cmd-box" id="(cmd-[^"]+)">\s*<header><h3><code>(.*?)</code>', body, re.S):
        items.append((m.start(), m.group(1), m.group(2), 1))
    return [i[1:] for i in sorted(items)]


def docs_nav_inner(slug, tests, body):
    cur = "/docs/" if slug == "docs" else f"/{slug}/"
    out = []
    toc = page_toc(body) if slug == "docs/console" else []
    if toc:
        rows, chips = "", ""
        for i, t, lv in toc + [("", "", 0)]:  # commands under a heading go on one wrapped line, to keep the list short
            if lv == 1:
                chips += f'<a href="#{i}">{html.escape(t)}</a>'
                continue
            if chips:
                rows += f'<li class="chips">{chips}</li>'
                chips = ""
            if i:
                rows += f'<li><a href="#{i}">{html.escape(t)}</a></li>'
        out.append(f'<h2>On this page</h2><ul class="side-list">{rows}</ul>')
    rows = "".join(f'<li><a href="{h}"{" aria-current=\"page\"" if h == cur else ""}>{html.escape(t)}</a></li>' for h, t in DOCS_GUIDES)
    out.append(f'<h2>Docs</h2><ul class="side-list">{rows}</ul>')
    here = next((c for c in tests["criteria"] if slug == f"docs/{c['slug']}"), None)
    groups = []
    for a in tests["areas"]:
        cs = [c for c in tests["criteria"] if c["area"] == a["name"]]
        li = "".join(f'<li><a href="/docs/{c["slug"]}/"{" aria-current=\"page\"" if c is here else ""}>{html.escape(c["title"])}</a></li>' for c in cs)
        opened = " open" if here and here["area"] == a["name"] else ""
        groups.append(f'<details class="side-area"{opened}><summary>{html.escape(a["name"])} <span>{len(cs)}</span></summary><ul class="side-list">{li}</ul></details>')
    out.append(f'<h2>Tests</h2>{"".join(groups)}')
    return "".join(out)


def docs_layout(slug, tests, body):
    inner = docs_nav_inner(slug, tests, body)
    return (f'<div class="docs-layout"><aside class="docs-side"><nav aria-label="Docs">{inner}</nav></aside>'
            f'<div class="docs-main"><details class="docs-menu"><summary>Docs menu</summary><nav aria-label="Docs, short list">{inner}</nav></details>'
            f'{body.strip()}</div></div>')


def document(cfg, rels, slug, title, desc, body, tests=None):
    path = "/" if slug == "index" else f"/{slug}/"
    section = "docs" if slug.startswith("docs/") or slug in GUIDES else slug
    nav = "".join(f'<a href="/{s}/"{" aria-current=\"page\"" if s == section else ""}>{t}</a>' for s, t in NAV)
    nav += f'<a class="out" href="{cfg["doesitomarchy"]}">DoesItOmarchy.com<span aria-hidden="true"> ↗</span></a>'
    nav += (f'<a class="repo" href="{cfg["repo"]}" rel="noopener">'
            f'<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="{OCTOCAT}"/></svg>{cfg["repo"].rsplit("/", 1)[1]}</a>')
    if slug not in WIDE:
        body = f'<div class="prose">{body.strip()}</div>'
    if tests and section == "docs":
        body = docs_layout(slug, tests, body)
    cls = "page-" + slug.replace("/", "-") + (" page-test" if slug.startswith("docs/") else "")
    full_title = cfg["name"] if slug == "index" else f"{title} · {cfg['name']}"
    url = cfg["site"] + path
    source = f' / {link(cfg["source"], "Source")}' if cfg["source"] else ""
    latest = newest(rels, "live")
    download = f'Download {html.escape(latest["version"])}' if latest else "Download"
    keys = ("".join(f'<span>{"Release" if c == "omaboot-release" else "Backup"} key <code>{fp}</code></span>' for _, _, _, c, fp in signers())
            or f'<span>Release keys: {FP_TBA}</span>')
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/site.css?v={asset_version("site.css")}">
<script src="/copy.js?v={asset_version("copy.js")}" defer></script>
<meta name="color-scheme" content="dark">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{cfg["name"]}">
<meta property="og:title" content="{html.escape(full_title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{cfg["site"]}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Will Omarchy run on your Mac? OmaBoot? Live's quick results on a MacBook Air.">
<meta name="twitter:card" content="summary_large_image">
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
  <p>OmaBoot? Live is made by the same people as <a href="{cfg["doesitomarchy"]}">DoesItOmarchy.com</a>.</p>
  <p><strong>A community site. Not officially affiliated with <a href="https://omarchy.org" rel="noopener">Omarchy</a> or the <a href="https://omarchy.org/foundation/" rel="noopener">Omacom Foundation</a>.</strong></p>
  <p class="links"><a href="/download/">{download}</a> / <a href="/write/">Flash a USB stick</a> / <a href="/verify/">Verify</a> / <a href="/fixes/">Fixes</a> / <a href="/docs/">Docs</a> / <a href="/privacy/">Privacy</a> / <a href="https://status.boot.watch">boot.watch status</a>{source}</p>
  <p class="keys"><a href="/verify/#keys">Signing keys</a> {keys}</p>
  <p class="fine">No cookies, no analytics, no third-party scripts.</p>
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
  Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'

/site.css
  Cache-Control: public, max-age=3600

/copy.js
  Cache-Control: public, max-age=3600

/assets/*
  Cache-Control: public, max-age=86400

/allowed_signers
  Content-Type: text/plain; charset=utf-8
  Cache-Control: public, max-age=300
"""


def build(out, releases_file, reports):
    cfg = json.load(open(os.path.join(DATA, "site.json")))
    rels = load_releases(releases_file, reports)
    todos = [f"data/site.json: {k[:-5]}: {v}" for k, v in cfg.items() if k.endswith("_TODO") and not cfg[k[:-5]]]
    assert os.path.basename(out) and os.path.abspath(out) not in (HERE, "/", os.path.expanduser("~"))
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    tests = load_tests()
    fixes = load_fixes()
    slugs = ["index"] + [s for s, _ in NAV] + FOOTER_ONLY
    pages = [(slug, *read_page(slug)) for slug in slugs + ["404"]]
    for slug, src in SUBPAGES.items():
        pages.append((slug, *read_page(src)))
    for c in tests["criteria"]:
        pages.append((f"docs/{c['slug']}", c["title"], f"How OmaBoot? Live tests {c['title'].lower()} ({c['id']}) on an Intel Mac, how it decides, and how sure it is.", test_body(tests, c, fixes)))
    for r in rels:
        if r.get("report"):
            pages.append((f"releases/{r['version']}", f"{r['version']} difference report",
                          f"OmaBoot? {r['version']} compared with the official Omarchy {r['omarchy']} ISO: every package and file that differs, and why.",
                          release_body(r, rels, cfg, fixes)))
    for slug, title, desc, body in pages:
        doc = document(cfg, rels, slug, title, desc, fill(body, cfg, rels, todos, slug, tests, fixes), tests)
        target = os.path.join(out, "404.html") if slug == "404" else os.path.join(out, "" if slug == "index" else slug, "index.html")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, "w").write(doc)
    slugs += list(SUBPAGES) + [f"docs/{c['slug']}" for c in tests["criteria"]] + [f"releases/{r['version']}" for r in rels if r.get("report")]
    shutil.copy2(os.path.join(HERE, "site.css"), os.path.join(out, "site.css"))
    shutil.copy2(os.path.join(HERE, "copy.js"), os.path.join(out, "copy.js"))
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
                p = href.split("#")[0].split("?")[0].lstrip("/")
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
    reports = argv[argv.index("--reports") + 1] if "--reports" in argv else os.path.join(DATA, "reports")
    build(out, releases, reports)


if __name__ == "__main__":
    main(sys.argv[1:])
