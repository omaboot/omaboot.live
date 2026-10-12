#!/usr/bin/env python3
"""Build omaboot.live: the public site of OmaBoot? Live. Static, no JavaScript, Python stdlib only.

Usage: site_build.py [--releases FILE] [--out DIR]
       site_build.py --serve [PORT] [--out DIR]

The build reads data/site.json (addresses), data/releases.json (published releases, newest
first; [] until the first one), data/allowed_signers (the release keys) and pages/*.html (the
copy: each page is an HTML fragment whose first lines are <!-- title: ... --> and
<!-- description: ... -->), and writes dist/: one directory per page, 404.html, site.css,
favicon.svg, allowed_signers, robots.txt, sitemap.xml, _headers and _redirects for Cloudflare
Pages. Boot and the OmaBoot? wordmark are drawn here as inline SVG from the prototype's pixels.

Tokens in pages: {{BOOT}} {{BOOT pleased}} (Boot's sprite), {{WORDMARK}}, {{DIO}} (a link to
DoesItOmarchy.com), {{RELEASE}} (the Download page's release section), {{SIGNERS}} (the keys),
{{FP_RELEASE}}, {{ISO}} (the newest ISO's file name), {{SOURCE}}, {{IMAGE_REPO}}, {{CONTACT ...}}.
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
# Navigation order; the slug is the URL path and the pages/ file name ("index" is /).
NAV = [("download", "Download"), ("write", "Write the stick"), ("verify", "Verify"), ("faq", "FAQ")]
FOOTER_ONLY = ["privacy"]  # linked from the footer, so the top line fits a phone

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
    return rels


def gb(n):
    return f"{n / 1e9:.1f} GB"


def release_html(rels):
    if not rels:
        return f'''<div class="say">{boot_svg(label="")}<p>not out yet. I'm still being tested on real Macs.</p></div>
<div class="soon">
  <p class="tag">Not released yet</p>
  <p><b>The first public release is coming soon.</b> There's no download yet, and test builds aren't shared.</p>
</div>
<h2>Each release comes with</h2>
<ul>
  <li>The image: one <code>.iso</code> file, about 2 GB.</li>
  <li><code>SHA256SUMS</code> and its signature, <code>SHA256SUMS.sig</code>, so you can <a href="/verify/">check the download</a>.</li>
  <li>The Omarchy release it's built from.</li>
  <li>The full package list, with versions.</li>
  <li>A difference report against the official Omarchy ISO of the same release.</li>
  <li>The public build log.</li>
</ul>
<p>Meanwhile, see which Macs are already tested on <a href="https://doesitomarchy.com">DoesItOmarchy.com</a>.</p>'''
    r = rels[0]
    name = r["iso"].rsplit("/", 1)[1]
    a = lambda k, t: f'<a href="{html.escape(r[k])}">{t}</a>'
    notes = f'<p>{html.escape(r["notes"])}</p>' if r.get("notes") else ""
    return f'''<div class="say">{boot_svg("pleased", label="")}<p>fresh build. check it before you write it.</p></div>
<div class="release">
  <p class="tag">OmaBoot? Live {html.escape(r["version"])} · {html.escape(r["date"])} · built from Omarchy {html.escape(r["omarchy"])}</p>
  {notes}
  <p class="get"><a class="button" href="{html.escape(r["iso"])}">Download</a> <span class="quiet"><code>{html.escape(name)}</code> · {gb(r["size"])}</span></p>
  <p class="tag">SHA256</p>
  <pre><code>{r["sha256"]}</code></pre>
  <ul class="files">
    <li>{a("sha256sums", "SHA256SUMS")}</li>
    <li>{a("signature", "SHA256SUMS.sig")}</li>
    <li><a href="/allowed_signers">allowed_signers</a></li>
    <li>{a("packages", "Package list")}</li>
    <li>{a("difference", "Difference report")}</li>
    <li>{a("build_log", "Build log")}</li>
  </ul>
</div>
<p>Next: <a href="/verify/">verify the download</a>, then <a href="/write/">write the stick</a>.</p>'''


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


def fill(body, cfg, rels, todos, slug):
    for t in re.findall(r"<!--\s*TODO\(owner\):(.*?)-->", body, re.S):
        todos.append(f"pages/{slug}.html: {' '.join(t.split())}")
    body = re.sub(r"\s*<!--\s*TODO\(owner\):.*?-->", "", body, flags=re.S)
    iso = rels[0]["iso"].rsplit("/", 1)[1] if rels else "omaboot-live-<version>.iso"
    rep = {
        "{{BOOT}}": boot_svg(label=""), "{{BOOT pleased}}": boot_svg("pleased", label=""),
        "{{WORDMARK}}": wordmark_svg(cls="wordmark big"),
        "{{DIO}}": f'<a href="{cfg["doesitomarchy"]}">DoesItOmarchy.com</a>',
        "{{OMARCHY}}": f'<a href="{cfg["omarchy"]}">omarchy.org</a>',
        "{{RELEASE}}": release_html(rels), "{{SIGNERS}}": signers_html(),
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
    nav = "".join(f'<a href="/{s}/"{" aria-current=\"page\"" if s == slug else ""}>{t}</a>' for s, t in NAV)
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
<meta name="color-scheme" content="light dark">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{cfg["name"]}">
<meta property="og:title" content="{html.escape(full_title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
</head>
<body class="page-{slug}">
<a class="skip" href="#main">Skip to content</a>
<header class="site">
  <a class="brand" href="/">{boot_svg(cls="boot mini", label="")}{wordmark_svg(label="OmaBoot? Live, home")}</a>
  <nav aria-label="Site">{nav}</nav>
</header>
<main id="main">
{body.strip()}
</main>
<footer class="site">
  <p>OmaBoot? Live is made by <a href="{cfg["doesitomarchy"]}">DoesItOmarchy.com</a>. It isn't an official Omarchy release.</p>
  <p><a href="/privacy/">Privacy</a> · No cookies, no analytics, no third-party scripts{source}</p>
</footer>
</body>
</html>
'''


# ── Output ──────────────────────────────────────────────────────────────────────────────────
HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Cross-Origin-Opener-Policy: same-origin
  Content-Security-Policy: default-src 'none'; script-src 'none'; style-src 'self'; img-src 'self'; font-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'

/site.css
  Cache-Control: public, max-age=3600

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
    slugs = ["index"] + [s for s, _ in NAV] + FOOTER_ONLY
    for slug in slugs + ["404"]:
        title, desc, body = read_page(slug)
        doc = document(cfg, slug, title, desc, fill(body, cfg, rels, todos, slug))
        target = os.path.join(out, "404.html") if slug == "404" else os.path.join(out, "" if slug == "index" else slug, "index.html")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, "w").write(doc)
    shutil.copy2(os.path.join(HERE, "site.css"), os.path.join(out, "site.css"))
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
