#!/usr/bin/env python3
"""Draw the OmaBoot? Live wordmark from BigBlue Terminal 437 (VileR, int10h.org; CC BY-SA 4.0) as
SVG outlines, so the site needs no font download for it. Writes data/wordmark.json, which
site_build.py turns into the inline SVG. The letters, being outlines of that font, are CC BY-SA 4.0
too (credited in README.md).

Needs fontTools (not the site build): tools/wordmark.py FONT.ttf
FONT: BigBlueTerm437NerdFontPropo-Regular.ttf from the Nerd Fonts release (BigBlueTerminal.tar.xz).
The font draws on an 8 x 12 pixel cell, 100 units a pixel, so the paths come out in pixels.
"""
import json, os, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

WORD = "OmaBoot? Live"
font = TTFont(sys.argv[1])
gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
unit = font["head"].unitsPerEm / 12  # one pixel of the 8 x 12 cell
x, letters, q, top, bottom = 0, [], [], 0, 0
for ch in WORD:
    name = cmap[ord(ch)]
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    if bp.bounds:
        top, bottom = max(top, bp.bounds[3]), min(bottom, bp.bounds[1])
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:g}")
    gs[name].draw(TransformPen(pen, (1 / unit, 0, 0, -1 / unit, x / unit, 0)))
    (q if ch == "?" else letters).append(pen.getCommands())
    x += hmtx[name][0]
out = {"source": "BigBlue Terminal 437 by VileR (int10h.org), CC BY-SA 4.0, via Nerd Fonts", "word": WORD,
       "x": 0, "y": -top / unit, "width": x / unit, "height": (top - bottom) / unit,
       "letters": " ".join(letters), "q": " ".join(q)}
json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "data", "wordmark.json"), "w"), indent=1)
print(out["width"], out["height"], out["y"])
