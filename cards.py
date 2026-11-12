#!/usr/bin/env python3
"""Leonida Daily card scenes: original motion-graphic cards.

Pillow draws animated frames, FFmpeg encodes them. No stock footage, no game footage.

A card scene in a manifest:
  {"type": "card", "layout": "stat", "duration": 6, "kicker": "...", "value": "212 GB",
   "sub": "...", "note": "...", "source": "Rockstar Support FAQ, 3 Nov 2026"}

Layouts : stat, versus, flow, list, bars, timeline, cta
Themes  : ink, paper, slate, ember (muted palettes, no neon)
Motifs  : grid, stripes, dots, rings
Theme and motif are picked per video from a seed (the video id) unless set in the manifest,
so consecutive videos do not look identical.

Layout fields
  all     : kicker, title, source (shown at the bottom, required for data cards)
  stat    : value (counts up if it holds a number), sub, note, tone (good|bad)
  versus  : left {label,value,sub,tone}, right {label,value,sub,tone}
  flow    : steps [{title,sub} | "text"]            (2-5 steps)
  list    : rows [{label,value,tone}], total {label,value}   (up to 6 rows)
  bars    : items [{label,value(number),display,highlight}]  (up to 5)
  timeline: events [{date,label,state: done|now|next}]       (up to 5)
  cta     : headline, comment, button

Test:
  python cards.py spec.json --preview out.jpg [--dur 6] [--seed V003]
  python cards.py spec.json out.mp4 [--dur 6] [--seed V003] [--w 1080 --h 1920]
"""
import functools
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

FPS = 30
RES = Image.Resampling.LANCZOS

THEMES = {
    "ink": {"bg": (21, 21, 24), "bg2": (36, 36, 41), "fg": (242, 239, 233), "accent": (200, 181, 138),
            "muted": (150, 146, 138), "panel": (45, 45, 51), "good": (126, 176, 126),
            "bad": (201, 92, 82), "on_accent": (26, 26, 26)},
    "paper": {"bg": (236, 232, 222), "bg2": (224, 219, 206), "fg": (28, 28, 28), "accent": (156, 112, 40),
              "muted": (112, 106, 96), "panel": (250, 247, 240), "good": (52, 116, 66),
              "bad": (172, 52, 46), "on_accent": (250, 247, 240)},
    "slate": {"bg": (23, 31, 43), "bg2": (35, 46, 62), "fg": (238, 240, 242), "accent": (214, 190, 150),
              "muted": (132, 144, 158), "panel": (43, 56, 73), "good": (120, 176, 140),
              "bad": (206, 98, 90), "on_accent": (23, 31, 43)},
    "ember": {"bg": (31, 23, 21), "bg2": (46, 34, 30), "fg": (245, 238, 230), "accent": (208, 128, 90),
              "muted": (156, 142, 132), "panel": (56, 42, 37), "good": (128, 172, 124),
              "bad": (214, 98, 84), "on_accent": (31, 23, 21)},
}
THEME_NAMES = list(THEMES)
MOTIFS = ["grid", "stripes", "dots", "rings"]
BUTTON_RED = (204, 0, 0)

# ----------------------------------------------------------------------------- fonts
_WEIGHTS = {
    "black": ["Montserrat-Black.ttf", "Montserrat-ExtraBold.ttf", "Montserrat-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "bold": ["Montserrat-Bold.ttf", "Montserrat-ExtraBold.ttf", "DejaVuSans-Bold.ttf"],
    "semi": ["Montserrat-SemiBold.ttf", "Montserrat-Medium.ttf", "Montserrat-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "reg": ["Montserrat-Medium.ttf", "Montserrat-Regular.ttf", "DejaVuSans.ttf"],
}
_FONT_DIRS = ["/usr/share/fonts/truetype/montserrat", "/usr/share/fonts/truetype", "/usr/share/fonts",
              os.path.expanduser("~/.fonts"), "C:/Windows/Fonts"]


@functools.lru_cache(None)
def _font_path(weight):
    for name in _WEIGHTS[weight]:
        for d in _FONT_DIRS:
            hit = glob.glob(os.path.join(d, "**", name), recursive=True)
            if hit:
                return hit[0]
    return None


@functools.lru_cache(None)
def font(size, weight="bold"):
    p = _font_path(weight)
    if p:
        return ImageFont.truetype(p, int(size))
    return ImageFont.load_default(int(size))


# ----------------------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(p):
    return 1 - (1 - p) ** 3


def mix(c1, c2, k):
    return tuple(int(c1[i] * (1 - k) + c2[i] * k) for i in range(3))


def wrap(s, f, max_w):
    out = []
    for para in str(s).split("\n"):
        cur = ""
        for wd in para.split():
            trial = (cur + " " + wd).strip()
            if f.getlength(trial) <= max_w or not cur:
                cur = trial
            else:
                out.append(cur)
                cur = wd
        out.append(cur)
    return out


SS = 3


def rrect_mask(w, h, r, stroke=0):
    w, h, r = max(int(w), 2), max(int(h), 2), max(int(r), 0)
    big = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r * SS, fill=255)
    if stroke:
        s = stroke * SS
        d.rounded_rectangle((s, s, w * SS - 1 - s, h * SS - 1 - s), radius=max(r - stroke, 0) * SS, fill=0)
    return big.resize((w, h), RES)


def ellipse_mask(dm, stroke=0):
    dm = max(int(dm), 2)
    big = Image.new("L", (dm * SS, dm * SS), 0)
    d = ImageDraw.Draw(big)
    d.ellipse((0, 0, dm * SS - 1, dm * SS - 1), fill=255)
    if stroke:
        s = stroke * SS
        d.ellipse((s, s, dm * SS - 1 - s, dm * SS - 1 - s), fill=0)
    return big.resize((dm, dm), RES)


def tri_down_mask(w, h):
    big = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(big).polygon([(0, 0), (w * SS, 0), (w * SS // 2, h * SS)], fill=255)
    return big.resize((w, h), RES)


class Item:
    def __init__(self, mask, color):
        self.mask, self.color = mask, color
        self.w, self.h = mask.size


class Sprite:
    """A solid colour drawn through a mask, with a simple entrance animation."""

    def __init__(self, mask, color, x, y, t0=0.0, d=0.45, kind="up"):
        self.mask, self.color = mask, color
        self.x, self.y = int(x), int(y)
        self.t0, self.d, self.kind = t0, d, kind
        self.solid = Image.new("RGB", mask.size, color)

    def draw(self, frame, t):
        p = ease_out(clamp((t - self.t0) / self.d))
        if p <= 0:
            return
        x, y, mask, solid, k = self.x, self.y, self.mask, self.solid, self.kind
        if k == "up":
            y += int((1 - p) * 50)
        elif k == "down":
            y -= int((1 - p) * 50)
        elif k == "left":
            x -= int((1 - p) * 110)
        elif k == "right":
            x += int((1 - p) * 110)
        alpha = p
        if k == "grow":
            wpx = max(1, int(mask.width * p))
            mask = mask.crop((0, 0, wpx, mask.height))
            solid = solid.crop((0, 0, wpx, mask.height))
            alpha = 1.0
        elif k == "pop":
            s = 0.8 + 0.2 * p
            nw, nh = max(1, int(mask.width * s)), max(1, int(mask.height * s))
            x += (self.mask.width - nw) // 2
            y += (self.mask.height - nh) // 2
            mask = mask.resize((nw, nh), Image.Resampling.BILINEAR)
            solid = Image.new("RGB", (nw, nh), self.color)
        if alpha < 0.999:
            mask = mask.point(lambda v, a=alpha: int(v * a))
        frame.paste(solid, (x, y), mask)


def parse_count(v):
    m = re.match(r"^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$", v)
    if not m:
        return None
    pre, num, suf = m.groups()
    return pre, float(num.replace(",", "")), suf, (len(num.split(".")[1]) if "." in num else 0), "," in num


class CountSprite:
    """Big number that counts up from zero. Falls back to static text when there is no number."""

    def __init__(self, cv, value, size, color, y, t0=0.15, dur=1.1):
        self.cv, self.color, self.y, self.t0, self.dur = cv, color, int(y), t0, dur
        self.value = value
        self.parsed = parse_count(value)
        size = cv.S(size)
        while size > 40 and font(size, "black").getlength(value) > cv.cw:
            size -= 6
        self.size = size
        self.f = font(size, "black")
        self.h = int(size * 1.25)
        self._cache = {}

    def _mask(self, s):
        if s not in self._cache:
            wpx = int(self.f.getlength(s)) + 8
            m = Image.new("L", (wpx, self.h), 0)
            ImageDraw.Draw(m).text((wpx / 2, 0), s, font=self.f, fill=255, anchor="ma")
            self._cache[s] = m
        return self._cache[s]

    def draw(self, frame, t):
        a = ease_out(clamp((t - self.t0) / 0.3))
        if a <= 0:
            return
        s = self.value
        if self.parsed:
            pre, num, suf, dec, comma = self.parsed
            cur = num * ease_out(clamp((t - self.t0) / self.dur))
            body = f"{cur:,.{dec}f}" if comma else f"{cur:.{dec}f}"
            s = pre + body + suf
        m = self._mask(s)
        if a < 0.999:
            m = m.point(lambda v, k=a: int(v * k))
        frame.paste(Image.new("RGB", m.size, self.color), (int(self.cv.cx - m.width / 2), self.y), m)


# ----------------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, theme, dur):
        self.w, self.h, self.t, self.dur = w, h, theme, dur
        self.portrait = h >= w
        self.u = 1.0 if self.portrait else 0.64
        self.mx = 70 if self.portrait else 150
        self.y0 = 230 if self.portrait else 110
        self.y1 = 1340 if self.portrait else h - 110
        self.cx = w // 2
        self.cw = min(w - 2 * self.mx, 940 if self.portrait else 1400)
        self.sprites = []
        self.image = None
        self.dim = 0.62
        self.bottom = self.y1 - self.S(80)

    def S(self, v):
        return int(round(v * self.u))

    # --- primitives
    def text(self, s, size, weight="bold", color=None, max_w=None, max_lines=2, align="center",
             upper=False, line_gap=1.0):
        color = color or self.t["fg"]
        s = str(s).upper() if upper else str(s)
        size = self.S(size)
        max_w = max_w or self.cw
        while True:
            f = font(size, weight)
            lines = wrap(s, f, max_w)
            fits = len(lines) <= max_lines and all(f.getlength(ln) <= max_w for ln in lines)
            if fits or size <= 26:
                break
            size -= 3
        lh = int(size * 1.22 * line_gap)
        wpx = int(max(f.getlength(ln) for ln in lines)) + 8
        m = Image.new("L", (wpx, lh * len(lines) + int(size * 0.25)), 0)
        d = ImageDraw.Draw(m)
        for i, ln in enumerate(lines):
            if align == "center":
                d.text((wpx / 2, i * lh), ln, font=f, fill=255, anchor="ma")
            elif align == "left":
                d.text((4, i * lh), ln, font=f, fill=255, anchor="la")
            else:
                d.text((wpx - 4, i * lh), ln, font=f, fill=255, anchor="ra")
        return Item(m, color)

    def panel(self, w, h, r, color, stroke=0):
        return Item(rrect_mask(w, h, r, stroke), color)

    def rect(self, w, h, color):
        return Item(Image.new("L", (max(int(w), 1), max(int(h), 1)), 255), color)

    def circle(self, dm, color, stroke=0):
        return Item(ellipse_mask(dm, stroke), color)

    def add(self, item, x, y, t0=0.0, d=0.45, kind="up", anchor="c"):
        left = x - item.w / 2 if anchor == "c" else (x if anchor == "l" else x - item.w)
        s = Sprite(item.mask, item.color, left, y, t0, d, kind)
        self.sprites.append(s)
        return s

    # --- shared furniture
    def header(self, spec):
        t, y = self.t, self.y0
        if spec.get("kicker"):
            self.add(self.rect(self.S(90), 8, t["accent"]), self.cx, y, 0.0, 0.5, "grow")
            y += self.S(30)
            it = self.text(spec["kicker"], 44, "bold", t["accent"], upper=True)
            self.add(it, self.cx, y, 0.05)
            y += it.h + self.S(18)
        if spec.get("title"):
            it = self.text(spec["title"], 70, "black", t["fg"], upper=True, max_lines=3)
            self.add(it, self.cx, y, 0.12)
            y += it.h + self.S(28)
        return y

    def footer(self, spec):
        if spec.get("source"):
            it = self.text("SOURCE: " + str(spec["source"]), 30, "semi", self.t["muted"], max_lines=2)
            self.add(it, self.cx, self.y1 - it.h, 0.6, 0.5, "fade")

    def center_stack(self, start, y_end):
        sp = self.sprites[start:]
        if not sp:
            return
        top = min(s.y for s in sp)
        zone = self.bottom - self.y0
        free = zone - (y_end - top)
        if free > 0:
            dy = int(free * 0.42) - (top - self.y0)
            for s in sp:
                s.y += dy

    def stagger(self, n, span=0.55, cap=0.45):
        return min(cap, (self.dur * span) / max(n, 1))


# ----------------------------------------------------------------------------- layouts
def _tone(t, name, default):
    return {"good": t["good"], "bad": t["bad"]}.get(name, default)


def L_stat(cv, spec):
    t, S = cv.t, cv.S
    y = cv.header(spec) + S(30)
    cs = CountSprite(cv, str(spec.get("value", "")), 280, _tone(t, spec.get("tone"), t["fg"]), y)
    cv.sprites.append(cs)
    y += cs.h + S(6)
    if spec.get("sub"):
        it = cv.text(spec["sub"], 66, "bold", t["accent"], upper=True)
        cv.add(it, cv.cx, y, 0.7)
        y += it.h + S(30)
    if spec.get("note"):
        cv.add(cv.rect(S(150), 6, mix(t["bg"], t["fg"], 0.3)), cv.cx, y, 0.85, 0.5, "grow")
        y += S(36)
        it = cv.text(spec["note"], 44, "reg", t["muted"], max_w=int(cv.cw * 0.92), max_lines=4)
        cv.add(it, cv.cx, y, 0.95)
        y += it.h
    return y


def L_versus(cv, spec):
    t, S = cv.t, cv.S
    y = cv.header(spec) + S(20)
    sides = [spec["left"], spec["right"]]
    gap = S(56) if cv.portrait else 120
    pw = cv.cw if cv.portrait else (cv.cw - gap) // 2
    built = []
    for sd in sides:
        pad = S(28)
        inner = pw - pad * 2 - S(14)
        tone = _tone(t, sd.get("tone"), t["accent"])
        lab = cv.text(sd.get("label", ""), 38, "semi", t["muted"], max_w=inner, max_lines=1, upper=True, align="left")
        val = cv.text(sd.get("value", ""), 100, "black", tone if sd.get("tone") else t["fg"], max_w=inner,
                      max_lines=1, upper=True, align="left")
        sub = cv.text(sd["sub"], 38, "reg", t["fg"], max_w=inner, max_lines=2, align="left") if sd.get("sub") else None
        h = pad + lab.h + S(6) + val.h + ((S(10) + sub.h) if sub else 0) + pad
        built.append((sd, pad, tone, lab, val, sub, h))
    ph = max(b[6] for b in built) if not cv.portrait else None
    ys = [y, y]
    if cv.portrait:
        ys[1] = y + built[0][6] + gap
    xs = [cv.cx - cv.cw // 2, cv.cx - cv.cw // 2] if cv.portrait else [cv.cx - cv.cw // 2, cv.cx - cv.cw // 2 + pw + gap]
    kinds = ["left", "right"]
    delays = [0.1, 0.5]
    for i, (sd, pad, tone, lab, val, sub, h) in enumerate(built):
        hh = h if cv.portrait else ph
        x0, y0_, t0, k = xs[i], ys[i], delays[i], kinds[i]
        cv.add(cv.panel(pw, hh, S(26), t["panel"]), x0, y0_, t0, 0.5, k, anchor="l")
        cv.add(cv.rect(S(12), hh - S(40), tone), x0 + S(14), y0_ + S(20), t0, 0.5, k, anchor="l")
        tx, ty = x0 + pad + S(14), y0_ + pad
        cv.add(lab, tx, ty, t0 + 0.08, 0.5, k, anchor="l")
        ty += lab.h + S(6)
        cv.add(val, tx, ty, t0 + 0.14, 0.5, k, anchor="l")
        ty += val.h + S(10)
        if sub:
            cv.add(sub, tx, ty, t0 + 0.22, 0.5, k, anchor="l")
    if cv.portrait:
        by = ys[0] + built[0][6] + gap // 2
        end = ys[1] + built[1][6]
    else:
        by = y + ph // 2
        end = y + ph
    bd = S(120)
    cv.add(cv.circle(bd, t["accent"]), cv.cx, by - bd // 2, 0.95, 0.35, "pop")
    vs = cv.text("VS", 50, "black", t["on_accent"], max_lines=1)
    cv.add(vs, cv.cx, by - vs.h // 2 - S(2), 0.95, 0.35, "pop")
    return end


def L_flow(cv, spec):
    t, S = cv.t, cv.S
    y = cv.header(spec) + S(16)
    steps = [s if isinstance(s, dict) else {"title": s} for s in spec["steps"]][:5]
    n = len(steps)
    arrow = S(54)
    avail = cv.bottom - y
    sh = int(min(S(210), (avail - (n - 1) * arrow) / n))
    dl = cv.stagger(n)
    for i, st in enumerate(steps):
        last = i == n - 1
        t0 = 0.2 + i * dl
        fill = mix(t["panel"], t["accent"], 0.16) if last else t["panel"]
        cv.add(cv.panel(cv.cw, sh, S(24), fill), cv.cx, y, t0, 0.45, "up")
        if last:
            cv.add(cv.panel(cv.cw, sh, S(24), t["accent"], stroke=3), cv.cx, y, t0, 0.45, "up")
        d = int(sh * 0.52)
        left = cv.cx - cv.cw // 2 + S(34)
        cv.add(cv.circle(d, t["accent"]), left, y + (sh - d) // 2, t0 + 0.05, 0.4, "pop", anchor="l")
        num = cv.text(str(i + 1), 44, "black", t["on_accent"], max_lines=1)
        cv.add(num, left + d // 2, y + (sh - num.h) // 2 - S(2), t0 + 0.05, 0.4, "pop")
        tx = left + d + S(30)
        inner = cv.cx + cv.cw // 2 - S(30) - tx
        ti = cv.text(st.get("title", ""), 46, "bold", t["fg"], max_w=inner, max_lines=2, upper=True, align="left")
        si = cv.text(st["sub"], 34, "reg", t["muted"], max_w=inner, max_lines=2, align="left") if st.get("sub") else None
        th = ti.h + ((S(6) + si.h) if si else 0)
        ty = y + (sh - th) // 2
        cv.add(ti, tx, ty, t0 + 0.1, 0.45, "up", anchor="l")
        if si:
            cv.add(si, tx, ty + ti.h + S(6), t0 + 0.16, 0.45, "up", anchor="l")
        y += sh
        if not last:
            aw, ah = S(46), S(28)
            cv.add(Item(tri_down_mask(aw, ah), t["accent"]), cv.cx, y + (arrow - ah) // 2, t0 + 0.25, 0.3, "fade")
            y += arrow
    return y


def L_list(cv, spec):
    t, S = cv.t, cv.S
    y = cv.header(spec) + S(10)
    rows = spec["rows"][:6]
    total = spec.get("total")
    n = len(rows)
    avail = cv.bottom - y - (S(160) if total else 0)
    rh = int(min(S(130), avail / max(n, 1)))
    dl = cv.stagger(n + (1 if total else 0))
    left = cv.cx - cv.cw // 2
    right = cv.cx + cv.cw // 2
    for i, r in enumerate(rows):
        t0 = 0.2 + i * dl
        lab = cv.text(r.get("label", ""), 46, "semi", t["fg"], max_w=int(cv.cw * 0.58), max_lines=2, align="left")
        val = cv.text(r.get("value", ""), 56, "black", _tone(t, r.get("tone"), t["accent"]),
                      max_w=int(cv.cw * 0.38), max_lines=1, upper=True, align="right")
        cv.add(lab, left, y + (rh - lab.h) // 2, t0, 0.45, "left", anchor="l")
        cv.add(val, right, y + (rh - val.h) // 2, t0 + 0.06, 0.45, "right", anchor="r")
        y += rh
        cv.add(cv.rect(cv.cw, 3, mix(t["bg"], t["fg"], 0.16)), cv.cx, y - 2, t0 + 0.1, 0.5, "grow", anchor="c")
    if total:
        y += S(28)
        t0 = 0.2 + n * dl
        th = S(132)
        cv.add(cv.panel(cv.cw, th, S(24), t["accent"]), cv.cx, y, t0, 0.45, "up")
        lab = cv.text(total.get("label", "TOTAL"), 48, "black", t["on_accent"], max_w=int(cv.cw * 0.5),
                      max_lines=1, upper=True, align="left")
        val = cv.text(total.get("value", ""), 62, "black", t["on_accent"], max_w=int(cv.cw * 0.4),
                      max_lines=1, upper=True, align="right")
        cv.add(lab, left + S(36), y + (th - lab.h) // 2, t0 + 0.08, 0.4, "up", anchor="l")
        cv.add(val, right - S(36), y + (th - val.h) // 2, t0 + 0.12, 0.4, "up", anchor="r")
        y += th
    return y


def L_bars(cv, spec):
    t, S = cv.t, cv.S
    y = cv.header(spec) + S(20)
    items = spec["items"][:5]
    mx = float(spec.get("max") or max(float(i["value"]) for i in items))
    dl = cv.stagger(len(items))
    left = cv.cx - cv.cw // 2
    right = cv.cx + cv.cw // 2
    for i, it in enumerate(items):
        t0 = 0.2 + i * dl
        hi = it.get("highlight", False)
        lab = cv.text(it.get("label", ""), 38, "semi", t["fg"] if hi else t["muted"], max_w=int(cv.cw * 0.6),
                      max_lines=1, upper=True, align="left")
        disp = it.get("display", str(it["value"]))
        val = cv.text(disp, 44, "black", t["accent"] if hi else t["fg"], max_w=int(cv.cw * 0.36),
                      max_lines=1, upper=True, align="right")
        cv.add(lab, left, y, t0, 0.4, "up", anchor="l")
        cv.add(val, right, y - S(4), t0 + 0.05, 0.4, "up", anchor="r")
        y += max(lab.h, val.h) + S(12)
        bh = S(52)
        cv.add(cv.panel(cv.cw, bh, bh // 2, t["panel"]), left, y, t0, 0.4, "fade", anchor="l")
        fw = max(int(cv.cw * float(it["value"]) / mx), bh)
        cv.add(cv.panel(fw, bh, bh // 2, t["accent"] if hi else mix(t["muted"], t["bg"], 0.35)),
               left, y, t0 + 0.1, 0.9, "grow", anchor="l")
        y += bh + S(46)
    return y - S(46)


def L_timeline(cv, spec):
    t, S = cv.t, cv.S
    y = cv.header(spec) + S(20)
    ev = spec["events"][:5]
    n = len(ev)
    avail = cv.bottom - y
    pitch = int(min(S(230), avail / n))
    dl = cv.stagger(n)
    lx = cv.cx - cv.cw // 2 + S(50)
    dd = S(46)
    cv.add(cv.rect(S(6), pitch * (n - 1), mix(t["bg"], t["fg"], 0.22)), lx, y + dd // 2, 0.15, 0.8, "fade")
    for i, e in enumerate(ev):
        t0 = 0.2 + i * dl
        yy = y + i * pitch
        st = e.get("state", "next")
        if st == "next":
            cv.add(cv.circle(dd, t["muted"], stroke=S(5)), lx, yy, t0, 0.4, "pop")
        else:
            cv.add(cv.circle(dd, t["accent"]), lx, yy, t0, 0.4, "pop")
            if st == "now":
                cv.add(cv.circle(dd + S(26), t["accent"], stroke=S(4)), lx - S(13), yy - S(13), t0 + 0.1, 0.5, "pop")
        tx = lx + dd // 2 + S(56)
        inner = cv.cx + cv.cw // 2 - tx
        di = cv.text(e.get("date", ""), 38, "bold", t["accent"], max_w=inner, max_lines=1, upper=True, align="left")
        li = cv.text(e.get("label", ""), 46, "semi", t["fg"] if st != "next" else t["muted"],
                     max_w=inner, max_lines=2, align="left")
        cv.add(di, tx, yy - S(6), t0 + 0.05, 0.45, "right", anchor="l")
        cv.add(li, tx, yy - S(6) + di.h + S(4), t0 + 0.12, 0.45, "right", anchor="l")
    return y + (n - 1) * pitch + dd + S(30)


def L_cta(cv, spec):
    t, S = cv.t, cv.S
    y = cv.y0 + S(60)
    pad = S(50)
    hl = cv.text(spec.get("headline", ""), 76, "black", t["bg"], max_w=cv.cw - 2 * pad, max_lines=3, upper=True)
    ph = hl.h + 2 * pad
    cv.add(cv.panel(cv.cw, ph, S(26), t["fg"]), cv.cx, y, 0.15, 0.5, "up")
    cv.add(hl, cv.cx, y + pad, 0.25, 0.5, "up")
    y += ph + S(50)
    cm = cv.text(spec.get("comment", "COMMENT BELOW"), 64, "bold", t["fg"], max_w=cv.cw - 2 * pad, max_lines=1, upper=True)
    ch = cm.h + S(70)
    cv.add(cv.panel(cv.cw, ch, S(26), t["panel"]), cv.cx, y, 0.45, 0.5, "up")
    cv.add(cm, cv.cx, y + S(35), 0.5, 0.5, "up")
    y += ch + S(50)
    bt = cv.text(spec.get("button", "SUBSCRIBE"), 80, "black", (255, 255, 255), max_w=cv.cw - 2 * pad, max_lines=1, upper=True)
    bh = bt.h + S(70)
    col = tuple(spec.get("button_color", BUTTON_RED))
    cv.add(cv.panel(cv.cw, bh, S(26), col), cv.cx, y, 0.9, 0.4, "pop")
    cv.add(bt, cv.cx, y + S(35), 0.9, 0.4, "pop")
    return y + bh


LAYOUTS = {"stat": L_stat, "versus": L_versus, "flow": L_flow, "list": L_list,
           "bars": L_bars, "timeline": L_timeline, "cta": L_cta}
CENTERED = {"stat", "versus", "flow", "list", "bars", "timeline"}


# ----------------------------------------------------------------------------- background
def _seed_int(seed):
    return int(hashlib.md5(str(seed).encode()).hexdigest(), 16)


def pick_style(theme, motif, seed):
    h = _seed_int(seed)
    th = theme if theme in THEMES else THEME_NAMES[h % len(THEME_NAMES)]
    mo = motif if motif in MOTIFS else MOTIFS[(h // 7) % len(MOTIFS)]
    return th, mo


def make_bg(w, h, t, motif):
    pad = 60
    W, H = w + pad, h + pad
    grad = Image.linear_gradient("L").resize((W, H), Image.Resampling.BILINEAR)
    img = Image.composite(Image.new("RGB", (W, H), t["bg2"]), Image.new("RGB", (W, H), t["bg"]), grad)
    d = ImageDraw.Draw(img)
    lc = mix(t["bg"], t["fg"], 0.06)
    if motif == "grid":
        for x in range(0, W, 60):
            d.line((x, 0, x, H), fill=lc, width=2)
        for y in range(0, H, 60):
            d.line((0, y, W, y), fill=lc, width=2)
    elif motif == "dots":
        for x in range(30, W, 60):
            for y in range(30, H, 60):
                d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=mix(t["bg"], t["fg"], 0.1))
    elif motif == "stripes":
        for k in range(-H, W, 60):
            d.line((k, H, k + H, 0), fill=lc, width=3)
    else:
        cx, cy = int(W * 0.78), int(H * 0.2)
        for r in range(120, 2600, 110):
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=lc, width=2)
    return img


# ----------------------------------------------------------------------------- public API
def build_canvas(spec, dur, w, h, theme=None, motif=None, seed=""):
    th, mo = pick_style(spec.get("theme") or theme, spec.get("motif") or motif, seed)
    cv = Canvas(w, h, THEMES[th], dur)
    cv.theme_name, cv.motif = th, mo
    if spec.get("source"):
        cv.bottom = cv.y1 - cv.S(150)
    layout = spec.get("layout", "stat")
    if layout not in LAYOUTS:
        raise ValueError(f"unknown card layout: {layout}")
    cv.art = load_art(spec["image"], w, h) if spec.get("image") and os.path.exists(spec["image"]) else None
    cv.dim = float(spec.get("image_dim", 0.62))
    y_end = LAYOUTS[layout](cv, spec)
    if layout in CENTERED:
        cv.center_stack(0, y_end)
    cv.footer(spec)
    return cv


def load_art(path, w, h):
    """Cover-fit an image to 1.18x the frame so it can slowly pan/zoom (Ken Burns)."""
    im = Image.open(path).convert("RGB")
    k = max(w * 1.18 / im.width, h * 1.18 / im.height)
    return im.resize((int(im.width * k) + 1, int(im.height * k) + 1), RES)


def art_frame(cv, art, t, w, h):
    z = 1.0 - 0.06 * clamp(t / max(cv.dur, 0.1))
    cw, ch = int(w * 1.18 * z / 1.18 * 1.18), int(h * 1.18 * z / 1.18 * 1.18)
    cw, ch = min(cw, art.width), min(ch, art.height)
    x0 = int((art.width - cw) * (0.35 + 0.3 * clamp(t / max(cv.dur, 0.1))))
    y0 = int((art.height - ch) * 0.5)
    fr = art.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.Resampling.BILINEAR)
    shade = Image.new("RGB", (w, h), cv.t["bg"])
    fr = Image.blend(fr, shade, cv.dim)
    grad = Image.linear_gradient("L").resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), cv.t["bg"]), fr, grad.point(lambda v: int(v * 0.55)))


def frame_at(cv, bg, t, w, h):
    if getattr(cv, "art", None) is not None:
        frame = art_frame(cv, cv.art, t, w, h)
        for s in cv.sprites:
            s.draw(frame, t)
        return frame
    if cv.motif == "rings":
        ox = oy = 0
    else:
        ox, oy = int((t * 9) % 60), int((t * 6) % 60)
    frame = bg.crop((ox, oy, ox + w, oy + h))
    for s in cv.sprites:
        s.draw(frame, t)
    return frame


def render_card_scene(spec, dur, dest, w=1080, h=1920, fps=FPS, theme=None, motif=None, seed=""):
    cv = build_canvas(spec, dur, w, h, theme, motif, seed)
    bg = make_bg(w, h, cv.t, cv.motif)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-t", f"{dur}", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "17", "-pix_fmt", "yuv420p", dest]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(round(dur * fps))):
        proc.stdin.write(frame_at(cv, bg, i / fps, w, h).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed while encoding card scene")
    return {"layout": spec.get("layout", "stat"), "theme": cv.theme_name, "motif": cv.motif}


def preview(spec, dur, out, w=1080, h=1920, seed="", theme=None):
    cv = build_canvas(spec, dur, w, h, theme, None, seed)
    bg = make_bg(w, h, cv.t, cv.motif)
    times = [0.3, 0.8, 1.6, max(dur - 0.1, 2.0)]
    tw = 360 if h >= w else 640
    th_ = int(tw * h / w)
    sheet = Image.new("RGB", (tw * len(times) + 10 * (len(times) - 1), th_), (0, 0, 0))
    for i, tt in enumerate(times):
        fr = frame_at(cv, bg, tt, w, h).resize((tw, th_), RES)
        sheet.paste(fr, (i * (tw + 10), 0))
    sheet.save(out, quality=88)
    return cv.theme_name, cv.motif


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(1)
    arg = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    spec = json.load(open(a[0]))
    dur = float(arg("--dur", 6))
    w, h = int(arg("--w", 1080)), int(arg("--h", 1920))
    if "--preview" in a:
        print(preview(spec, dur, arg("--preview"), w, h, arg("--seed", ""), arg("--theme")))
    else:
        print(render_card_scene(spec, dur, a[1], w, h, theme=arg("--theme"), seed=arg("--seed", "")))
