#!/usr/bin/env python3
"""Iconify icons (200k+ open-source icons, no API key) as transparent PNG layers.

    python3 iconify.py search bell [--limit 12]       # find icon names
    python3 iconify.py png lucide:bell out.png 128 [--color FFD64D]

Used by render_reel.py for `{"kind": "icon", "icon": "lucide:bell", "size": 120, "color": "yellow"}`.
SVG and collection info are cached in ~/.cache/pich/iconify/. The collection's license and
author are recorded with every render (manifest overlays) so attribution is available if a set needs it.
Monotone icons take `color`; multicolor sets (emoji, logos) keep their own palette.
"""
import json, os, re, sys, tempfile, urllib.error, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_logos import svg_to_png  # noqa: E402

API = "https://api.iconify.design"
CACHE = Path.home() / ".cache" / "pich" / "iconify"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_BYTES = 512 * 1024  # an icon SVG is a few KB; refuse anything big before it reaches a native parser


def _get(url, what):
    req = urllib.request.Request(url, headers={"User-Agent": "pich/0.7"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404: raise ValueError(f"{what} not found on Iconify")
        raise RuntimeError(f"Iconify request failed for {what}: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Iconify unreachable ({e.reason}) while fetching {what}") from e
    if len(data) > MAX_BYTES: raise ValueError(f"{what}: response over {MAX_BYTES // 1024} KB, refused")
    return data


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "wb") as f: f.write(data)
    os.replace(tmp, path)


def check_name(icon):
    if not isinstance(icon, str) or len(icon) > 96 or not NAME.fullmatch(icon):
        raise ValueError(f"icon must look like 'prefix:name' (e.g. lucide:bell), got {icon!r}")
    return icon.split(":")


def check_svg(data, what):
    t = data.decode("utf-8", "replace")
    if not t.lstrip().startswith("<svg") or re.search(r"<!ENTITY|<!DOCTYPE|<image\b|<foreignObject|(?:xlink:)?href\s*=\s*[\"'](?!#)", t, re.I):
        raise ValueError(f"{what}: SVG has external references/unsupported content, refused")
    vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', t)
    if vb and float(vb.group(2)) > 0 and not (1 / 6 <= float(vb.group(1)) / float(vb.group(2)) <= 6):
        raise ValueError(f"{what}: aspect ratio outside 1:6..6:1, refused")


def collection_info(prefix):
    f = CACHE / f"{prefix}.info.json"
    try: info = json.loads(f.read_text()) if f.exists() else None
    except ValueError: info = None  # corrupt cache entry -> refetch once
    if info is None:
        try: d = json.loads(_get(f"{API}/collection?prefix={prefix}&info=true", f"collection {prefix!r}"))
        except ValueError as e: raise ValueError(f"unknown Iconify collection {prefix!r}") from e
        if "info" not in d: raise ValueError(f"unknown Iconify collection {prefix!r}")
        info = d["info"]; _atomic_write(f, json.dumps(info, ensure_ascii=False).encode())
    return {"collection": info.get("name", prefix), "license": (info.get("license") or {}).get("spdx") or (info.get("license") or {}).get("title"),
            "license_url": (info.get("license") or {}).get("url"), "author": (info.get("author") or {}).get("name"),
            "author_url": (info.get("author") or {}).get("url")}


def icon_png(icon, out, size, color_hex=None):
    """Fetch (cached) and rasterize to a `size`-px-tall transparent PNG. Returns (path, (w, h), provenance)."""
    prefix, name = check_name(icon)
    if not isinstance(size, int) or not 16 <= size <= 800: raise ValueError("icon size must be an integer 16..800")
    q = {"height": "auto"}
    if color_hex is not None:
        if not isinstance(color_hex, str) or not re.fullmatch(r"[0-9A-Fa-f]{6}", color_hex): raise ValueError(f"bad color {color_hex!r}")
        q["color"] = "#" + color_hex.upper()
    variant = (color_hex or "orig").lower()  # separate path component per color: no name/color collisions
    svg = CACHE / prefix / name / f"{variant}.svg"
    data = svg.read_bytes() if svg.exists() else None
    if data is None:
        data = _get(f"{API}/{prefix}/{name}.svg?{urllib.parse.urlencode(q)}", f"icon {icon!r}")
        check_svg(data, f"icon {icon!r}"); _atomic_write(svg, data)
    else:
        check_svg(data, f"icon {icon!r}")
    try: svg_to_png(svg, out, size)
    except Exception:  # possibly a corrupt cached file: refetch once
        svg.unlink(missing_ok=True)
        data = _get(f"{API}/{prefix}/{name}.svg?{urllib.parse.urlencode(q)}", f"icon {icon!r}"); check_svg(data, f"icon {icon!r}"); _atomic_write(svg, data)
        svg_to_png(svg, out, size)
    from PIL import Image
    with Image.open(out) as im: wh = im.size
    return Path(out), wh, dict(collection_info(prefix), icon=icon, source=f"{API}/{prefix}/{name}.svg")


def main():
    a = sys.argv[1:]
    if a[:1] == ["search"] and len(a) >= 2:
        lim = int(a[a.index("--limit") + 1]) if "--limit" in a else 12
        d = json.loads(_get(f"{API}/search?query={urllib.parse.quote(a[1])}&limit={max(32, lim)}"))
        for n in d.get("icons", [])[:lim]: print(n)
    elif a[:1] == ["png"] and len(a) >= 4:
        col = a[a.index("--color") + 1] if "--color" in a else None
        p, wh, prov = icon_png(a[1], a[2], int(a[3]), col); print(p, wh, prov["license"], prov["collection"])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
