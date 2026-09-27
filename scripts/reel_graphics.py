#!/usr/bin/env python3
"""PIL templates for Reel layers.

Every template takes its text and a `tokens` dict instead of hardcoded copy, so a
plan.json can drive it (tests pin the output to a golden filter graph).
All text is rendered with an OFL font (Manrope by default); no generated lettering.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FONT = SKILL_DIR / "assets" / "fonts" / "Manrope.ttf"

DEFAULT_TOKENS = {
    "ink": [16, 19, 26], "navy": [20, 24, 33], "accent": [47, 91, 255],
    "paper": [243, 241, 236], "yellow": [255, 214, 77], "teal": [120, 214, 255],
    "chip_icon": [140, 168, 255], "eyebrow": [150, 175, 255],
}


class Style:
    def __init__(self, tokens=None, font_path=None, width=1080, height=1920):
        t = dict(DEFAULT_TOKENS, **(tokens or {}))
        self.c = {k: tuple(v) for k, v in t.items()}
        self.font_path = str(font_path or DEFAULT_FONT)
        self.W, self.H = width, height

    def font(self, size, wght=800):
        f = ImageFont.truetype(self.font_path, size)
        try: f.set_variation_by_axes([wght])
        except OSError: pass  # static font: weight comes from the file itself
        return f


def _tracked(d, x, y, text, f, fill, track):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + track
    return x


# ---------------- captions ----------------
CAPTION_BOX_H = 260


def wrap(text, f, maxw):
    words = text.split(); lines = [""]
    for w_ in words:
        t = (lines[-1] + " " + w_).strip()
        if f.getlength(t) <= maxw: lines[-1] = t
        else: lines.append(w_)
    return lines


def caption_png(st, text, hl, path, size=62, maxw=900, lh=76):
    f = st.font(size, 800); lines = wrap(text, f, maxw)
    im = Image.new("RGBA", (st.W, CAPTION_BOX_H), (0, 0, 0, 0))
    y0 = (CAPTION_BOX_H - lh * len(lines)) // 2
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines):
        x = (st.W - f.getlength(ln)) / 2; y = y0 + i * lh
        sd.text((x, y + 4), ln, font=f, fill=(0, 0, 0, 170), stroke_width=8, stroke_fill=(0, 0, 0, 170))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(6))); d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        x = (st.W - f.getlength(ln)) / 2; y = y0 + i * lh
        for wd in ln.split(" "):
            col = st.c["yellow"] if wd in hl else (255, 255, 255)
            d.text((x, y), wd, font=f, fill=col, stroke_width=6, stroke_fill=(12, 12, 16))
            x += f.getlength(wd + " ")
    im.save(path)
    return CAPTION_BOX_H


# ---------------- icons (vector, drawn; no generated imagery) ----------------
ICONS = ("image", "code", "gear", "nodes", "chat", "arrow_down", "arrow_right")


def icon(kind, size, col, lw=None):
    if ":" in kind:  # Iconify name (e.g. lucide:hourglass), tinted to `col`
        import tempfile
        import iconify
        out = Path(tempfile.mkdtemp()) / "i.png"
        iconify.icon_png(kind, out, size, "%02X%02X%02X" % tuple(col[:3]))
        im = Image.open(out).convert("RGBA"); im.thumbnail((size, size), Image.LANCZOS)
        c = Image.new("RGBA", (size, size), (0, 0, 0, 0)); c.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
        return c
    if kind not in ICONS:
        raise ValueError(f"unknown icon {kind!r}; choose from {ICONS} or an Iconify name like lucide:bell")
    s = size * 4; im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lw = lw or int(s * 0.075); m = int(s * 0.12)
    if kind == "image":
        d.rounded_rectangle([m, m + s * .08, s - m, s - m - s * .08], radius=s * .1, outline=col, width=lw)
        d.polygon([(m + lw, s - m - s * .08 - lw), (s * .42, s * .45), (s * .6, s * .63), (s * .7, s * .52), (s - m - lw, s - m - s * .08 - lw)], fill=col)
        d.ellipse([s * .6, s * .27, s * .74, s * .41], fill=col)
    elif kind == "code":
        d.line([(s * .34, s * .28), (s * .14, s * .5), (s * .34, s * .72)], fill=col, width=lw, joint="curve")
        d.line([(s * .66, s * .28), (s * .86, s * .5), (s * .66, s * .72)], fill=col, width=lw, joint="curve")
        d.line([(s * .56, s * .22), (s * .44, s * .78)], fill=col, width=lw)
    elif kind == "gear":
        c = s / 2; R = s * .30; teeth = 8
        for k in range(teeth):
            a = k * 2 * math.pi / teeth
            pts = []
            for da, r in ((-.2, R), (-.13, R + s * .12), (.13, R + s * .12), (.2, R)):
                pts.append((c + r * math.cos(a + da), c + r * math.sin(a + da)))
            d.polygon(pts, fill=col)
        d.ellipse([c - R, c - R, c + R, c + R], fill=col)
        d.ellipse([c - R * .45, c - R * .45, c + R * .45, c + R * .45], fill=(0, 0, 0, 0))
    elif kind == "nodes":
        P = [(s * .5, s * .2), (s * .2, s * .75), (s * .8, s * .75)]
        for i in range(3):
            d.line([P[i], P[(i + 1) % 3]], fill=col, width=lw)
        for p in P:
            r = s * .12; d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col)
    elif kind == "chat":
        d.rounded_rectangle([m, m + s * .05, s - m, s * .7], radius=s * .14, outline=col, width=lw)
        d.polygon([(s * .3, s * .68), (s * .3, s * .88), (s * .5, s * .68)], fill=col)
        for k in range(3):
            x = s * (.34 + k * .16); d.ellipse([x - s * .045, s * .4 - s * .045, x + s * .045, s * .4 + s * .045], fill=col)
    elif kind == "arrow_down":
        d.line([(s / 2, s * .12), (s / 2, s * .82)], fill=col, width=lw)
        d.line([(s * .24, s * .56), (s / 2, s * .84), (s * .76, s * .56)], fill=col, width=lw, joint="curve")
    elif kind == "arrow_right":
        d.line([(s * .12, s / 2), (s * .82, s / 2)], fill=col, width=lw)
        d.line([(s * .56, s * .24), (s * .84, s / 2), (s * .56, s * .76)], fill=col, width=lw, joint="curve")
    return im.resize((size, size), Image.LANCZOS)


def shadowed(card, blur=18, off=8, alpha=90, pad=40):
    w_, h_ = card.size
    out = Image.new("RGBA", (w_ + pad * 2, h_ + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    mask = card.split()[3].point(lambda v: alpha if v > 0 else 0)
    sh.paste((0, 0, 0, 255), (pad, pad + off), mask)
    out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(card, (pad, pad))
    return out, pad


# ---------------- cards (return (size, shadow_pad)) ----------------
def hook_card(st, path, eyebrow, text_from, text_to):
    """Top hook: tracked eyebrow + 'from -> to' line. Visible on frame 0."""
    w_, h_ = 860, 132
    c = Image.new("RGBA", (w_, h_), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    d.rounded_rectangle([0, 0, w_ - 1, h_ - 1], radius=34, fill=st.c["navy"] + (238,))
    fe = st.font(26, 700); fm = st.font(46, 800)
    need = max(44 + fm.getlength(text_from) + 16 + 44 + 16 + fm.getlength(text_to) + 44,
               88 + sum(fe.getlength(ch) + 4 for ch in eyebrow))
    if need > w_: raise ValueError(f"hook text too long ({need:.0f}px > {w_}px): shorten '{text_from} -> {text_to}'")
    _tracked(d, 44, 20, eyebrow, fe, st.c["eyebrow"], 4)
    ar = icon("arrow_right", 44, st.c["yellow"])
    x = 44; d.text((x, 56), text_from, font=fm, fill=(255, 255, 255)); x += fm.getlength(text_from) + 16
    c.alpha_composite(ar, (int(x), 66)); x += 44 + 16
    d.text((x, 56), text_to, font=fm, fill=st.c["yellow"])
    im, pad = shadowed(c); im.save(path); return im.size, pad


def wordmark(st, path, text):
    """Font-rendered tracked wordmark, no left bar, faded centered hairline. No shadow pad."""
    f = st.font(76, 500); track = 22
    wlen = sum(f.getlength(ch) for ch in text) + track * (len(text) - 1)
    w_, h_ = int(wlen + 120), 150
    c = Image.new("RGBA", (w_, h_), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    x = 60
    for ch in text:
        d.text((x, 22), ch, font=f, fill=st.c["ink"]); x += f.getlength(ch) + track
    y = 118; x0, x1 = 60 + wlen * .25, 60 + wlen * .75
    for i in range(int(x0), int(x1)):
        t = (i - x0) / (x1 - x0); a = int(255 * math.sin(math.pi * t))
        d.line([(i, y), (i, y + 2)], fill=st.c["accent"] + (a,))
    c.save(path); return c.size, 0


def cta_card(st, path, lines, pill):
    """Separate CTA card (never styled like a caption): 2 lines + white pill with down arrow."""
    w_, h_ = 900, 240
    c = Image.new("RGBA", (w_, h_), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    d.rounded_rectangle([0, 0, w_ - 1, h_ - 1], radius=40, fill=st.c["accent"] + (255,))
    f1 = st.font(48, 800); f2 = st.font(34, 700)
    if len(lines) != 2: raise ValueError("CTA needs exactly 2 lines")
    for t in lines:
        if f1.getlength(t) > w_ - 60: raise ValueError(f"CTA line too long: {t!r}")
    if f2.getlength(pill) + 12 + 34 + 48 > w_ - 60: raise ValueError(f"CTA pill too long: {pill!r}")
    for t, y in zip(lines[:2], (26, 84)):
        d.text(((w_ - f1.getlength(t)) / 2, y), t, font=f1, fill=(255, 255, 255))
    tw = f2.getlength(pill) + 12 + 34; x = (w_ - tw) / 2
    d.rounded_rectangle([x - 24, 164, x + tw + 24, 214], radius=24, fill=(255, 255, 255, 255))
    d.text((x, 166), pill, font=f2, fill=st.c["accent"])
    c.alpha_composite(icon("arrow_down", 34, st.c["accent"]), (int(x + f2.getlength(pill) + 12), 172))
    im, pad = shadowed(c, blur=20, off=10, alpha=110); im.save(path); return im.size, pad


def image_card(st, src, path, width, radius=34):
    """Frame a supplied/generated image as a rounded popup card with thin border + shadow."""
    img = Image.open(src).convert("RGBA")
    h_ = round(width * img.height / img.width)
    img = img.resize((width, h_), Image.LANCZOS)
    m = Image.new("L", (width * 4, h_ * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, width * 4 - 1, h_ * 4 - 1], radius=radius * 4, fill=255)
    img.putalpha(m.resize((width, h_), Image.LANCZOS))
    d = ImageDraw.Draw(img); d.rounded_rectangle([1, 1, width - 2, h_ - 2], radius=radius, outline=st.c["teal"] + (200,), width=3)
    im, pad = shadowed(img, blur=18, off=8, alpha=110); im.save(path); return im.size, pad


def icon_card(st, icon_path, path, pad=26, radius=30):
    """Supplied icon PNG centered on a navy rounded card with soft shadow (same family as the step chips)."""
    ic = Image.open(icon_path).convert("RGBA")
    c = Image.new("RGBA", (ic.width + pad * 2, ic.height + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(c).rounded_rectangle([0, 0, c.width - 1, c.height - 1], radius=radius, fill=st.c["navy"] + (236,))
    c.alpha_composite(ic, (pad, pad))
    im, sp = shadowed(c, blur=12, off=6, alpha=70, pad=24); im.save(path); return im.size, sp


def round_badge(st, src, path, size):
    img = Image.open(src).convert("RGBA")
    c = int(img.width * 0.2); img = img.crop((c, c, img.width - c, img.height - c)).resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    img.putalpha(m.resize((size, size), Image.LANCZOS))
    im, pad = shadowed(img, blur=14, off=6, alpha=90, pad=30); im.save(path); return im.size, pad


# ---------------- full-frame explanatory stepper slide + PiP ----------------
def stepper_slides(st, paths, eyebrow, title, steps, pip):
    """One PNG per active step. steps: [(icon, 'First rest words')]; pip: (x, y, w, h).
    Steps light up in sync with speech; the PiP window keeps the face visible."""
    W, H = st.W, st.H; TEAL = st.c["teal"]; n = len(steps)
    for active, path in enumerate(paths):
        im = Image.new("RGBA", (W, H), (15, 22, 36, 255)); d = ImageDraw.Draw(im)
        orb = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(orb)
        od.ellipse([620, -260, 1240, 360], fill=st.c["accent"] + (70,))
        im = Image.alpha_composite(im, orb.filter(ImageFilter.GaussianBlur(60))); d = ImageDraw.Draw(im)
        _tracked(d, 64, 250, eyebrow, st.font(28, 700), TEAL, 5)
        ft = st.font(80, 800)
        d.text((64, 296), title[0], font=ft, fill=(255, 255, 255))
        d.text((64, 392), title[1], font=ft, fill=st.c["yellow"])
        px, py, pw, ph = pip
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle([px, py + 12, px + pw, py + ph + 12], radius=44, fill=(0, 0, 0, 150))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(20))); d = ImageDraw.Draw(im)
        d.rounded_rectangle([px - 5, py - 5, px + pw + 5, py + ph + 5], radius=48, outline=TEAL + (255,), width=4)
        x0, y0, cw, chh, gap = 56, 540, 492, 126, 32
        cx_line = x0 + 46
        d.line([(cx_line, y0 + chh // 2), (cx_line, y0 + (n - 1) * (chh + gap) + chh // 2)], fill=(60, 74, 100, 255), width=4)
        if active > 0:
            d.line([(cx_line, y0 + chh // 2), (cx_line, y0 + active * (chh + gap) + chh // 2)], fill=TEAL + (255,), width=4)
        fn = st.font(30, 800); fl = st.font(38, 800)
        for i, (k, lab) in enumerate(steps):
            y = y0 + i * (chh + gap)
            if i == active:
                fill, outline, tcol, icol, ncol = (34, 70, 110, 255), TEAL + (255,), (255, 255, 255), TEAL, (15, 22, 36)
            elif i < active:
                fill, outline, tcol, icol, ncol = (26, 38, 58, 255), (60, 90, 120, 255), (200, 212, 228), (150, 190, 220), (15, 22, 36)
            else:
                fill, outline, tcol, icol, ncol = (22, 30, 46, 255), (40, 52, 72, 255), (110, 122, 142), (90, 104, 128), (15, 22, 36)
            d.rounded_rectangle([x0 + 90, y, x0 + cw, y + chh], radius=26, fill=fill, outline=outline, width=3)
            r = 30; ccol = TEAL if i <= active else (60, 74, 100)
            d.ellipse([cx_line - r, y + chh // 2 - r, cx_line + r, y + chh // 2 + r], fill=ccol + (255,))
            num = f"{i + 1:02d}"; d.text((cx_line - fn.getlength(num) / 2, y + chh // 2 - 20), num, font=fn, fill=ncol)
            im.alpha_composite(icon(k, 56, icol), (x0 + 116, y + (chh - 56) // 2)); d = ImageDraw.Draw(im)
            words = lab.split(" ")
            d.text((x0 + 190, y + 18), words[0], font=fl, fill=tcol)
            d.text((x0 + 190, y + 64), " ".join(words[1:]), font=st.font(32, 600), fill=tcol)
        im.save(path)


def video_frame(path, w, h, radius=34, outline=None, width=3):
    """Shadow + rounded outline ring (transparent inside) to lay over a video card / PiP of size w x h."""
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=(0, 0, 0, 255))
    im, pad = shadowed(card, blur=18, off=8, alpha=110)
    hole = Image.new("L", im.size, 0); ImageDraw.Draw(hole).rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=radius, fill=255)
    a = im.split()[3].point(lambda v: v); a.paste(0, mask=hole); im.putalpha(a)  # keep only the shadow outside the card
    if outline: ImageDraw.Draw(im).rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=radius, outline=outline + (230,), width=width)
    im.save(path); return im.size, pad


def pip_mask(path, w, h, radius=42):
    m = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=radius * 4, fill=255)
    m.resize((w, h), Image.LANCZOS).save(path)
