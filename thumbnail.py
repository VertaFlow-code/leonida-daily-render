#!/usr/bin/env python3
"""Leonida Daily Short thumbnail (9:16, 1080x1920 JPG, well under YouTube's size limits).

Usage: python thumbnail.py manifests/V003.json thumbs/V003.jpg

Manifest block (all optional except line2):
  "thumbnail": {"kicker": "GTA 6 · XBOX ONE", "line1": "XBOX ONE", "line2": "CAN'T INSTALL",
                "line3": "GTA 6", "badge": "STREAM ONLY"}
line2 is the big accent line. Same theme/motif as the video (picked from the video id), so the
thumbnail matches the Short. Keep it to 2-4 words per line: it must read at thumbnail size.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

import cards
from cards import THEMES, font, make_bg, mix, pick_style, wrap

W, H = 1080, 1920


def fit(draw, text, weight, max_w, start, lo=60):
    size = start
    while size > lo and font(size, weight).getlength(text) > max_w:
        size -= 4
    return font(size, weight), size


def stroke_text(draw, xy, text, f, fill, outline, width=10):
    draw.text(xy, text, font=f, fill=fill, anchor="mm", stroke_width=width, stroke_fill=outline)


def make(mf, out):
    tb = mf.get("thumbnail") or {}
    seed = mf.get("id", "")
    th, mo = pick_style(mf.get("card_theme"), mf.get("card_motif"), seed)
    t = THEMES[th]
    img = make_bg(W, H, t, mo).crop((0, 0, W, H)).convert("RGB")
    d = ImageDraw.Draw(img)
    ink = (14, 14, 16)
    cx = W // 2
    maxw = W - 160

    y = 570
    if tb.get("kicker"):
        f, _ = fit(d, tb["kicker"].upper(), "bold", maxw, 54, 36)
        d.rectangle((cx - 60, y - 70, cx + 60, y - 62), fill=t["accent"])
        d.text((cx, y), tb["kicker"].upper(), font=f, fill=t["accent"], anchor="mm")
        y += 150
    if tb.get("line1"):
        f, sz = fit(d, tb["line1"].upper(), "black", maxw, 170, 80)
        stroke_text(d, (cx, y + sz // 2), tb["line1"].upper(), f, t["fg"], ink, 9)
        y += sz + 40
    f, sz = fit(d, tb["line2"].upper(), "black", maxw, 210, 90)
    lines = wrap(tb["line2"].upper(), f, maxw)
    for ln in lines:
        stroke_text(d, (cx, y + sz // 2), ln, f, t["accent"], ink, 11)
        y += int(sz * 1.08)
    y += 30
    if tb.get("line3"):
        f, sz = fit(d, tb["line3"].upper(), "black", maxw, 190, 80)
        stroke_text(d, (cx, y + sz // 2), tb["line3"].upper(), f, t["fg"], ink, 9)
        y += sz + 40
    if tb.get("badge"):
        f, sz = fit(d, tb["badge"].upper(), "black", maxw - 120, 70, 40)
        tw = int(f.getlength(tb["badge"].upper())) + 100
        bh = int(sz * 1.9)
        y += 30
        d.rounded_rectangle((cx - tw // 2, y, cx + tw // 2, y + bh), radius=bh // 2, fill=t["accent"])
        d.text((cx, y + bh // 2), tb["badge"].upper(), font=f, fill=t["on_accent"], anchor="mm")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    img.save(out, quality=90)
    return out


if __name__ == "__main__":
    mf = json.load(open(sys.argv[1]))
    mf.setdefault("id", os.path.splitext(os.path.basename(sys.argv[1]))[0])
    if "thumbnail" not in mf:
        mf["thumbnail"] = {"line2": mf.get("title", mf["id"])}
    print(make(mf, sys.argv[2]))
