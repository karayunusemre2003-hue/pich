#!/usr/bin/env python3
"""(Re)build the verified logo library from Simple Icons (CC0 icon data; each icon records the brand's
official source page). Writes assets/logos/<slug>.png (brand color) and <slug>-white.png + manifest.json.

    python3 fetch_logos.py [slug ...]                     # Simple Icons; default: common AI / social brands
    python3 fetch_logos.py --brandfetch openai.com openai  # Brandfetch; only brands CLAIMED by their owner

Brands missing from Simple Icons (e.g. OpenAI, removed at its request) can come from Brandfetch (free key:
https://developers.brandfetch.com -> env BRANDFETCH_API_KEY), accepted only when the brand owner has claimed
the profile. Unclaimed profiles are refused — check those by eye and add by hand. Never thumbnails or AI
generations. Trademarks stay with their owners: use a logo only when the speaker names that brand.
"""
import datetime, json, os, re, subprocess, sys, tempfile, urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
LOGOS = Path(os.environ.get("PICH_LOGOS_DIR", SKILL / "assets" / "logos")).expanduser()
CDN = "https://cdn.jsdelivr.net/npm/simple-icons@latest"
DEFAULT = ["claude", "anthropic", "googlegemini", "whatsapp", "instagram", "telegram", "tiktok", "youtube", "github",
           "obsidian", "n8n", "elevenlabs", "perplexity", "cursor", "meta", "x", "notion", "figma", "mistralai",
           "deepseek", "huggingface"]
SVG2PNG = Path.home() / ".cache" / "pich" / "svg2png"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pich/0.7"})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read()


def svg2png_bin():
    src = SKILL / "scripts" / "svg2png.swift"
    if not SVG2PNG.exists() or SVG2PNG.stat().st_mtime < src.stat().st_mtime:
        SVG2PNG.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(src), "-o", str(SVG2PNG)], check=True, capture_output=True)
    return SVG2PNG


def svg_to_png(svg, png, height):
    """Rasterize: macOS AppKit helper; elsewhere rsvg-convert or CairoSVG (e.g. the Linux VPS)."""
    import shutil
    if sys.platform == "darwin":
        subprocess.run([str(svg2png_bin()), str(svg), str(png), str(height)], check=True, capture_output=True); return
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-h", str(height), "-o", str(png), str(svg)], check=True, capture_output=True); return
    try:
        import cairosvg
    except ImportError:
        raise RuntimeError("no SVG rasterizer: install librsvg (rsvg-convert) or `pip install cairosvg`")
    cairosvg.svg2png(url=str(svg), write_to=str(png), output_height=height)


def slug_of(i):
    if i.get("slug"): return i["slug"]
    t = i["title"].lower().replace("+", "plus").replace(".", "dot").replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", t)


def brandfetch(domain, slug):
    import json as _j
    key = os.environ.get("BRANDFETCH_API_KEY")
    if not key: sys.exit("set BRANDFETCH_API_KEY (free key: https://developers.brandfetch.com)")
    req = urllib.request.Request(f"https://api.brandfetch.io/v2/brands/{domain}",
                                 headers={"Authorization": f"Bearer {key}", "User-Agent": "pich/0.7"})
    with urllib.request.urlopen(req, timeout=30) as r: d = _j.load(r)
    if not d.get("claimed"): sys.exit(f"{domain}: Brandfetch profile is NOT claimed by the brand — refusing; verify by eye and add by hand")
    logos = d.get("logos", [])
    pick = [l for t in ("symbol", "logo") for l in logos if l["type"] == t]
    if not pick: sys.exit(f"{domain}: no symbol/logo on Brandfetch")
    typ = pick[0]["type"]; man_p = LOGOS / "manifest.json"; man = _j.loads(man_p.read_text()); out = {}
    from PIL import Image
    for l in (x for x in logos if x["type"] == typ):
        fmt = next((f for f in l["formats"] if f["format"] == "svg"), None) or next((f for f in l["formats"] if f["format"] == "png"), None)
        if not fmt: continue
        tmp = Path(tempfile.mkdtemp()) / f"x.{fmt['format']}"; tmp.write_bytes(get(fmt["src"]))
        png = Path(tempfile.mkdtemp()) / "x.png"
        svg_to_png(tmp, png, 256)
        with Image.open(png) as im:  # decide which background it is for by the brightness of its visible pixels
            b = im.convert("RGBA").tobytes(); px = [tuple(b[i:i + 4]) for i in range(0, len(b), 4) if b[i + 3] > 128]
        lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, _ in px) / max(1, len(px))
        key = f"{slug}-white" if lum > 160 else slug
        png.replace(LOGOS / f"{key}.png")
        out[key] = {"file": f"{key}.png", "title": d.get("name"), "type": typ, "theme": l.get("theme"),
                    "source_url": f"https://brandfetch.com/{domain}", "icon_source": fmt["src"] + " (Brandfetch, brand-claimed)",
                    "verified_at": datetime.date.today().isoformat(), "notes": "Owner-claimed Brandfetch profile; use only when the brand is named."}
    if len(out) == 1:  # one theme only: a single-color mark can be recolored for the other background
        (have, meta), = out.items(); other = f"{slug}-white" if have == slug else slug
        with Image.open(LOGOS / meta["file"]) as im:
            im = im.convert("RGBA"); b = im.tobytes()
            cols = {b[i:i + 3] for i in range(0, len(b), 4) if b[i + 3] > 200}
            if len({tuple(v // 32 for v in c) for c in cols}) <= 2:
                fill = (255, 255, 255) if other.endswith("-white") else (0, 0, 0)
                Image.merge("RGBA", (*Image.new("RGB", im.size, fill).split(), im.getchannel("A"))).save(LOGOS / f"{other}.png")
                out[other] = dict(meta, file=f"{other}.png", notes=meta["notes"] + " Recolored single-color copy of the claimed mark.")
            else: print(f"  {other}: multicolor mark, not recolored — add the other theme by hand if needed")
    man["logos"].update(out); man_p.write_text(_j.dumps(man, indent=1, ensure_ascii=False) + "\n")
    print(f"+ {domain} -> {sorted(out)} ({typ})")


def main():
    if sys.argv[1:2] == ["--brandfetch"]:
        if len(sys.argv) != 4: sys.exit("usage: fetch_logos.py --brandfetch DOMAIN SLUG")
        if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", sys.argv[2]) or not re.fullmatch(r"[a-z0-9-]+", sys.argv[3]): sys.exit("bad domain/slug")
        return brandfetch(sys.argv[2], sys.argv[3])
    slugs = sys.argv[1:] or DEFAULT
    data = json.loads(get(f"{CDN}/data/simple-icons.json")); data = data.get("icons", data) if isinstance(data, dict) else data
    idx = {slug_of(i): i for i in data}
    man_p = LOGOS / "manifest.json"; man = json.loads(man_p.read_text()); logos = man.setdefault("logos", {})
    today = datetime.date.today().isoformat(); tmp = Path(tempfile.mkdtemp())
    for s in slugs:
        i = idx.get(s)
        if not i: print(f"- {s}: not in Simple Icons, add by hand"); continue
        svg = get(f"{CDN}/icons/{s}.svg").decode()
        for key, color in ((s, i["hex"]), (f"{s}-white", "FFFFFF")):
            f = tmp / f"{key}.svg"; f.write_text(svg.replace("<svg ", f'<svg fill="#{color}" ', 1))
            svg_to_png(f, LOGOS / f"{key}.png", 256)
            logos[key] = {"file": f"{key}.png", "title": i["title"], "hex": color, "source_url": i.get("source", ""),
                          "icon_source": f"{CDN}/icons/{s}.svg (Simple Icons, CC0)", "guidelines": i.get("guidelines", ""),
                          "verified_at": today, "notes": "Monochrome brand mark; use only when the brand is named."}
        print(f"+ {s} ({i['title']})")
    man_p.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
