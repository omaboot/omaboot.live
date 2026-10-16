#!/usr/bin/env python3
"""A blueprint-style line drawing of the iMac (27-inch, Late 2009) [iMac10,1] from the rear left,
for omaboot.live's hero (owner's pick D3, 2026-10-16: the ports labelled with the tests that check them). A small 3D model (mm) projected in perspective; hidden lines removed with
SVG masks (the stand hides the back, the back and stand hide the foot).

World: X along the back as seen from behind (0 = the edge with the ports), Y up from the desk,
Z out of the back (0 = the front glass). Port places: omarchaeology gen/portmaps.yaml, chassis
imac-2009-27 (ma1206 p22), shapes after gen/portmaps.py's glyphs.

Usage: tools/hero_drawing.py OUT.svg [--labels none|numbers|tests] [--az 38] [--el 20] [--zoom 1.0] ...
The hero's drawing: tools/hero_drawing.py data/hero-imac.svg --labels tests --hero
(site_build.py inlines it on the home page, so it takes the page's colour and fonts).
"""
import argparse
import math

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--labels", default="none")
ap.add_argument("--az", type=float, default=38)
ap.add_argument("--el", type=float, default=20)
ap.add_argument("--dist", type=float, default=1500)
ap.add_argument("--zoom", type=float, default=1.0)
ap.add_argument("--target", default="260,170,40")
ap.add_argument("--w", type=int, default=1600)
ap.add_argument("--h", type=int, default=900)
ap.add_argument("--cx", type=float, default=0.5, help="where the target lands across the frame (0-1)")
ap.add_argument("--cy", type=float, default=0.5)
ap.add_argument("--hatch", type=int, default=1)
ap.add_argument("--hero", action="store_true", help="the home page's framing and markup")
a = ap.parse_args()
if a.hero:  # the framing picked on the review page (D3), for a wide, short hero
    # the port row lands under the hero's laptop, its labels to the right of it (site.css sizes the
    # drawing 1440 x 1530 px, centred on the page and standing on the hero's bottom edge; tall enough
    # that the iMac's edges run up to the menu bar on any hero)
    a.zoom, a.target, a.cx, a.cy, a.az, a.el, a.w, a.h = 2.3, "112,110,20", 0.585, 1 - 92 / 1700, 55, 12, 1600, 1700

W, H, Y0 = 650.0, 447.0, 70.0          # body width, height, gap under it
TE, B, R = 12.0, 48.0, 20.0            # edge band depth, back bulge, corner radius
PORT_Y = Y0 + 25
PORTS = [  # x, kind, rotation (portmaps.yaml back row)
    (58.7, "audio", 0), (69.9, "audio", 0), (81.7, "usb", 270), (94, "usb", 270), (106.3, "usb", 270),
    (118.6, "usb", 270), (133.5, "fw800", 0), (147.95, "mdp", 90), (162.8, "eth", 0)]
STAND_W, HINGE_Y, FOOT_Z0, FOOT_Z1, FOOT_T = 205.0, 250.0, 25.0, 205.0, 5.0


def px(s): return max(0.0, 1 - abs(2 * s - 1) ** 4)
def py(s): return max(0.0, 1 - abs(2 * s - 1) ** 3)


def inside(x, y):
    """Signed distance-ish test for the rounded rectangle in XY."""
    cx = min(max(x, R), W - R); cy = min(max(y, Y0 + R), Y0 + H - R)
    return (x - cx) ** 2 + (y - cy) ** 2 <= R * R + 1e-6 and 0 <= x <= W and Y0 <= y <= Y0 + H


def zb(x, y):
    return TE + B * px(x / W) * py((y - Y0) / H)


def grad(x, y, e=0.5):
    return ((zb(x + e, y) - zb(x - e, y)) / (2 * e), (zb(x, y + e) - zb(x, y - e)) / (2 * e))


# ── camera ──
tx, ty, tz = map(float, a.target.split(","))
az, el = math.radians(a.az), math.radians(a.el)
d = (-math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
C = (tx + a.dist * d[0], ty + a.dist * d[1], tz + a.dist * d[2])
def sub(p, q): return (p[0] - q[0], p[1] - q[1], p[2] - q[2])
def dot(p, q): return p[0] * q[0] + p[1] * q[1] + p[2] * q[2]
def cross(p, q): return (p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0])
def norm(p):
    l = math.sqrt(dot(p, p)); return (p[0] / l, p[1] / l, p[2] / l)
fwd = norm(sub((tx, ty, tz), C)); right = norm(cross(fwd, (0, 1, 0))); up = cross(right, fwd)
F = a.zoom * 1.25 * a.w


def P(p):
    v = sub(p, C); z = dot(v, fwd)
    return (a.w * a.cx + F * dot(v, right) / z, a.h * a.cy - F * dot(v, up) / z)


def poly(pts, close=False):
    s = "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in (P(p) for p in pts))
    return s + (" Z" if close else "")


def outline(n=24):
    """XY points around the rounded rectangle, counter-clockwise from the bottom-left corner's end."""
    pts = []
    corners = [(W - R, Y0 + R, -90), (W - R, Y0 + H - R, 0), (R, Y0 + H - R, 90), (R, Y0 + R, 180)]
    for cx, cy, a0 in corners:
        for i in range(n + 1):
            t = math.radians(a0 + 90 * i / n)
            pts.append((cx + R * math.cos(t), cy + R * math.sin(t)))
    return pts


O = outline()
body_lines, foot_lines, stand_lines, faint = [], [], [], []

# back edge (z = TE) all round, and the front edge (z = 0) where it shows: up the port edge, along the top
body_lines.append(poly([(x, y, TE) for x, y in O], close=True))
n = 24
# from the start of the bottom-left arc, up the port edge, across the top to the top-right arc's middle
front_pts = O[3 * (n + 1):3 * (n + 1) + 1] + O[2 * (n + 1):3 * (n + 1)][::-1] + O[n + 1:2 * (n + 1)][::-1][: n // 2 + 1]
body_lines.append(poly([(x, y, 0) for x, y in front_pts]))
# the band's corner lines (where the arcs meet the straight sides) read as edges in a line drawing
for i in (3 * (n + 1), 2 * (n + 1) + n, 2 * (n + 1), n + 1 + n):
    x, y = O[i]
    if x < W / 2 or y > Y0 + H / 2:
        body_lines.append(poly([(x, y, 0), (x, y, TE)]))

# shell contours: rows of constant Y, closer together near the top and bottom (patent shading)
rows = []
k = 16
for i in range(1, k):
    s = i / k
    s = 0.5 - 0.5 * math.cos(math.pi * s)
    rows.append(Y0 + H * s)
for y in rows:
    xs = [x for x in [j * W / 160 for j in range(161)] if inside(x, y)]
    if len(xs) < 2:
        continue
    pts = [(x, y, zb(x, y)) for x in xs]
    (body_lines if a.hatch == 2 else faint).append(poly(pts))
# a few columns near the port edge, where the back curves most
for x in ([10, 30, 60] if a.hatch else []):
    ys = [y for y in [Y0 + j * H / 120 for j in range(121)] if inside(x, y)]
    faint.append(poly([(x, y, zb(x, y)) for y in ys]))
# the top vent: a long slot just under the top edge
vy = Y0 + H - 16
for dy in (0, 3.2):
    xs = [80 + j * (W - 160) / 80 for j in range(81)]
    body_lines.append(poly([(x, vy + dy, zb(x, vy + dy)) for x in xs]))
for x in (80, W - 80):
    body_lines.append(poly([(x, vy, zb(x, vy)), (x, vy + 3.2, zb(x, vy + 3.2))]))


# ── ports, on the back's tangent plane at each port ──
def rr(x0, y0, w, h, r, n=4):
    pts = []
    for cx, cy, a0 in ((x0 + w - r, y0 + r, -90), (x0 + w - r, y0 + h - r, 0), (x0 + r, y0 + h - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            t = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def circ(cx, cy, r, n=28):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def glyph(kind):
    """Closed outlines in mm, x right, y up, centred."""
    if kind == "audio":
        return [circ(0, 0, 3.6), circ(0, 0, 1.9)]
    if kind == "usb":
        return [rr(-6.5, -2.8, 13, 5.6, .6), rr(-5.55, -2.8 + 1.25, 11.1, 1.84, .25)]
    if kind == "mdp":
        return [[(-3.75, 2.3), (3.75, 2.3), (3.75, -1.3), (2.75, -2.3), (-2.75, -2.3), (-3.75, -1.3)],
                rr(-2.7, -.6, 5.4, 1.2, .3)]
    if kind == "fw800":
        return [rr(-5.4, -4.05, 10.8, 8.1, .6), [(-3.65, 2.45), (-.45, 2.45), (-.45, .55), (.45, .55), (.45, 2.45), (3.65, 2.45), (3.65, -1.75), (-3.65, -1.75)]]
    if kind == "eth":
        return [[(-5.85, 4.4), (5.85, 4.4), (5.85, -2.6), (3.1, -2.6), (3.1, -4.4), (-3.1, -4.4), (-3.1, -2.6), (-5.85, -2.6)]]
    return []


port_lines, port_anchor = [], []
for x, kind, rot in PORTS:
    y = PORT_Y
    gx, gy = grad(x, y)
    u = norm((1, 0, gx)); nrm = norm((-gx, -gy, 1)); v = cross(nrm, u)
    c, s = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))
    for ring in glyph(kind):
        pts = []
        for lx, ly in ring:
            rx, ry = lx * c - ly * s, lx * s + ly * c
            pts.append((x + rx * u[0] + ry * v[0], y + rx * u[1] + ry * v[1], zb(x, y) + rx * u[2] + ry * v[2] + 0.2))
        port_lines.append(poly(pts, close=True))
    port_anchor.append((x, kind, P((x, y + 8, zb(x, y + 8)))))

# ── stand: a plate from the hinge down to the desk, then the foot forward under the display ──
xs0, xs1 = W / 2 - STAND_W / 2, W / 2 + STAND_W / 2
zh = zb(W / 2, HINGE_Y)
top, bot = (HINGE_Y, zh), (FOOT_T, FOOT_Z1)
def plate(x, t, off=0.0):
    """A point on the plate's back face, t from 0 (hinge) to 1 (desk); off pushes it out of the face."""
    yy = top[0] + (bot[0] - top[0]) * t; zz = top[1] + (bot[1] - top[1]) * t
    ny, nz = (bot[1] - top[1]), -(bot[0] - top[0]); l = math.hypot(ny, nz)
    return (x, yy + off * ny / l, zz + off * nz / l)
TH = 6.0
plate_face = [plate(xs0, 0, TH), plate(xs1, 0, TH), plate(xs1, 1, TH), plate(xs0, 1, TH)]
stand_lines.append(poly(plate_face, close=True))
stand_lines.append(poly([plate(xs0, 0, 0), plate(xs0, 1, 0)]))          # the plate's edge, port side
stand_lines.append(poly([plate(xs0, 0, 0), plate(xs0, 0, TH)]))
stand_lines.append(poly([plate(xs0, 1, 0), plate(xs0, 1, TH)]))
# the cable hole
ht, hr = 0.74, 21.0
hc = plate(W / 2, ht, TH)
L = math.hypot(bot[0] - top[0], bot[1] - top[1])
def hole(r, off):
    pts = []
    for i in range(48):
        t = 2 * math.pi * i / 48
        p = plate(W / 2 + r * math.cos(t), ht + r * math.sin(t) / L, off)
        pts.append(p)
    return pts
hole_out = hole(hr, TH)
stand_lines.append(poly(hole_out, close=True))
stand_lines.append(poly(hole(hr, 0), close=True))
# the foot: a slab on the desk from the bend forward
foot_top = [(xs0, FOOT_T, FOOT_Z0), (xs1, FOOT_T, FOOT_Z0), (xs1, FOOT_T, FOOT_Z1), (xs0, FOOT_T, FOOT_Z1)]
foot_lines.append(poly(foot_top, close=True))
foot_lines.append(poly([(xs0, 0, FOOT_Z0), (xs0, 0, FOOT_Z1), (xs1, 0, FOOT_Z1)]))
for p in [(xs0, FOOT_T, FOOT_Z0), (xs0, FOOT_T, FOOT_Z1), (xs1, FOOT_T, FOOT_Z1)]:
    foot_lines.append(poly([p, (p[0], 0, p[2])]))


# ── silhouettes for hiding ──
def hull(pts):
    pts = sorted(set(pts))
    def cr(o, a_, b_): return (a_[0] - o[0]) * (b_[1] - o[1]) - (a_[1] - o[1]) * (b_[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cr(hi[-2], hi[-1], p) <= 0: hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]
body_pts = [P((x, y, 0)) for x, y in O] + [P((x, y, zb(x, y))) for x in [j * W / 40 for j in range(41)]
                                           for y in [Y0 + j * H / 30 for j in range(31)] if inside(x, y)]
body_sil = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in hull(body_pts)) + " Z"
plate_sil = poly(plate_face, close=True) + " " + poly(hole_out, close=True)
# include the plate's thickness strip on the port side in its silhouette
plate_sil += " " + poly([plate(xs0, 0, 0), plate(xs0, 1, 0), plate(xs0, 1, TH), plate(xs0, 0, TH)], close=True)

# ── labels ──
labels = []   # (anchor x, y, elbow x, y, end x, y, text, anchor)
NAMES = ["audio.headphones", "audio.line-in", "ports.usb-a", None, None, None, "ports.firewire",
         "graphics.external-display", "network.ethernet"]
if a.labels == "tests":
    # each leader rises from its port, then runs right to a column of names: the leftmost port's
    # name on top, so no two leaders cross
    named = [(i, t) for i, t in enumerate(NAMES) if t]
    low = min(ly for _, _, (lx, ly) in port_anchor) - 18
    col_x = max(lx for _, _, (lx, ly) in port_anchor) + 48
    for k_, (i, t) in enumerate(named):
        lx, ly = port_anchor[i][2]
        ey = low - 24 * (len(named) - 1 - k_)
        labels.append((lx, ly, lx, ey, col_x, ey, t, "start"))
elif a.labels == "numbers":
    for i, (x, kind, (lx, ly)) in enumerate(port_anchor):
        if i in (3, 4, 5):
            continue
        ex, ey = lx - 10 + 3 * i, ly - 54 - (22 if i % 2 else 0)
        labels.append((lx, ly, ex, ey, ex, ey, str(110 + 2 * i), "middle"))
w, h = a.w, a.h
root = ('class="hero-art" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false" ' if a.hero else "")
out = [f'<svg xmlns="http://www.w3.org/2000/svg" {root}viewBox="0 0 {w} {h}" fill="none" stroke="currentColor" '
       f'stroke-linecap="round" stroke-linejoin="round">',
       '<defs>',
       f'<mask id="hm-body" maskUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="#fff"/>'
       f'<path d="{plate_sil}" fill="#000" fill-rule="evenodd" stroke="none"/></mask>',
       f'<mask id="hm-foot" maskUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="#fff"/>'
       f'<path d="{body_sil}" fill="#000" stroke="none"/><path d="{plate_sil}" fill="#000" fill-rule="evenodd" stroke="none"/></mask>',
       '</defs>']
out.append(f'<g mask="url(#hm-foot)" stroke-width="1.1">' + "".join(f'<path d="{d}"/>' for d in foot_lines) + '</g>')
out.append(f'<g mask="url(#hm-body)">')
out.append('<g stroke-width="0.7" opacity="0.55">' + "".join(f'<path d="{d}"/>' for d in faint) + '</g>')
out.append('<g stroke-width="1.3">' + "".join(f'<path d="{d}"/>' for d in body_lines) + '</g>')
out.append('<g stroke-width="0.9">' + "".join(f'<path d="{d}"/>' for d in port_lines) + '</g>')
out.append('</g>')
out.append('<g stroke-width="1.3">' + "".join(f'<path d="{d}"/>' for d in stand_lines) + '</g>')
if labels:
    out.append('<g stroke-width="0.8">' + "".join(f'<path d="M{lx:.1f},{ly:.1f} L{bx:.1f},{by:.1f} L{ex:.1f},{ey:.1f}"/><circle cx="{lx:.1f}" cy="{ly:.1f}" r="1.6" fill="currentColor"/>' for lx, ly, bx, by, ex, ey, _, _ in labels) + '</g>')
    out.append('<g class="labels" fill="currentColor" stroke="none" font-size="15">'
               + "".join(f'<text x="{ex + (8 if an == "start" else -8 if an == "end" else 0):.0f}" y="{ey + (5 if an != "middle" else -8):.0f}" text-anchor="{an}">{t}</text>' for _, _, _, _, ex, ey, t, an in labels) + '</g>')
if a.labels in ("numbers", "tests") and not a.hero:
    out.append(f'<text x="{w * 0.08:.0f}" y="{h * 0.92:.0f}" fill="currentColor" stroke="none" font-size="16" letter-spacing="2">FIG. 1  iMac10,1</text>')
out.append('</svg>')
open(a.out, "w").write("\n".join(out))
print(a.out, "C=", tuple(round(c) for c in C))
