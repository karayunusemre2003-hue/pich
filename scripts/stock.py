#!/usr/bin/env python3
"""Pexels stock photos/videos for popup cards and B-roll (free key: https://www.pexels.com/api/ -> env PEXELS_API_KEY).

    python3 stock.py search "people working in office" [--video] [--orientation portrait|landscape|square] [--limit 8]
    python3 stock.py get 6272871 --video --out PROJECT/assets     # or --photo
    python3 stock.py sheet "tomato market" --out /tmp/x.jpg        # contact sheet of photo results to choose from

Downloads go to your project folder with a sidecar <file>.json: Pexels id, page URL, photographer,
license (Pexels License: free, no attribution required; don't imply endorsement by people/brands shown,
don't resell unaltered). Use a photo via `{"kind": "image_card", "src": ..., "provenance": "stock"}`.
The renderer composes still images only; stock *video* is downloaded for later B-roll use.
"""
import argparse, datetime, json, os, re, sys, tempfile, urllib.parse, urllib.request
from pathlib import Path

API = "https://api.pexels.com"
LICENSE = "Pexels License — https://www.pexels.com/license/"


def key():
    k = os.environ.get("PEXELS_API_KEY")
    if not k: sys.exit("set PEXELS_API_KEY (free key: https://www.pexels.com/api/)")
    return k


def api(path, **q):
    req = urllib.request.Request(f"{API}{path}?{urllib.parse.urlencode(q)}", headers={"Authorization": key(), "User-Agent": "jarvis-video-studio/0.5"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-video-studio/0.5"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20): f.write(chunk)


def search(query, video, orientation, limit):
    q = {"query": query, "per_page": min(80, max(1, limit))}
    if orientation: q["orientation"] = orientation
    d = api("/videos/search" if video else "/v1/search", **q)
    rows = []
    for it in d.get("videos" if video else "photos", [])[:limit]:
        who = it["user"]["name"] if video else it["photographer"]
        rows.append({"id": it["id"], "w": it["width"], "h": it["height"], "dur": it.get("duration"), "by": who, "url": it["url"],
                     "thumb": it["image"] if video else it["src"]["medium"]})
    return rows


def get(item_id, video, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    if video:
        it = api(f"/videos/videos/{int(item_id)}")
        files = [f for f in it["video_files"] if f.get("file_type") == "video/mp4" and f.get("width")]
        # the biggest file whose long side is <= 3840 (skip 8K monsters)
        f = max((f for f in files if max(f["width"], f["height"]) <= 3840), key=lambda f: f["width"] * f["height"])
        link, ext, who, who_url = f["link"], "mp4", it["user"]["name"], it["user"]["url"]; size = [f["width"], f["height"]]
    else:
        it = api(f"/v1/photos/{int(item_id)}")
        link, ext, who, who_url = it["src"]["original"], "jpg", it["photographer"], it["photographer_url"]; size = [it["width"], it["height"]]
    dest = out / f"pexels-{int(item_id)}.{ext}"
    if dest.exists(): sys.exit(f"refuse to overwrite {dest}")
    download(link, dest)
    if video:  # Pexels metadata can disagree with the file (seen: "uhd 2160x3840" that is really 1440x2560) -> measure it
        import subprocess
        pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                                 "stream=width,height,r_frame_rate", "-of", "json", str(dest)]))["streams"][0]
        size = [pr["width"], pr["height"]]; fps = pr["r_frame_rate"]
    else:
        from PIL import Image
        with Image.open(dest) as im: size = list(im.size)
        fps = None
    meta = {"source": "Pexels", "id": int(item_id), "kind": "video" if video else "photo", "page_url": it["url"], "file_url": link,
            "size": size, **({"fps": fps} if fps else {}), "author": who, "author_url": who_url, "license": LICENSE, "downloaded_at": datetime.date.today().isoformat()}
    Path(str(dest) + ".json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    return dest, meta


def sheet(query, out, orientation, limit=12):
    from PIL import Image, ImageDraw
    rows = search(query, False, orientation, limit); tiles = []
    for r in rows:
        f = Path(tempfile.mkdtemp()) / "t.jpg"; download(r["thumb"], f)
        im = Image.open(f).convert("RGB"); im.thumbnail((300, 300)); tiles.append((r["id"], im))
    cols = 4; rows_n = (len(tiles) + cols - 1) // cols
    s = Image.new("RGB", (cols * 310, rows_n * 330), (20, 24, 33)); d = ImageDraw.Draw(s)
    for i, (pid, im) in enumerate(tiles):
        x, y = (i % cols) * 310 + 5, (i // cols) * 330 + 5; s.paste(im, (x, y)); d.text((x, y + 305), str(pid), fill=(255, 214, 77))
    s.save(out, quality=88); return out


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("search"); a1.add_argument("query"); a1.add_argument("--video", action="store_true")
    a1.add_argument("--orientation", choices=["portrait", "landscape", "square"]); a1.add_argument("--limit", type=int, default=8)
    a2 = sub.add_parser("get"); a2.add_argument("id", type=int); g = a2.add_mutually_exclusive_group(required=True)
    g.add_argument("--video", action="store_true"); g.add_argument("--photo", action="store_true"); a2.add_argument("--out", required=True)
    a3 = sub.add_parser("sheet"); a3.add_argument("query"); a3.add_argument("--out", required=True)
    a3.add_argument("--orientation", choices=["portrait", "landscape", "square"])
    a = ap.parse_args()
    if a.cmd == "search":
        for r in search(a.query, a.video, a.orientation, a.limit):
            print(f"{r['id']:>10}  {r['w']}x{r['h']}" + (f"  {r['dur']}s" if r["dur"] else "") + f"  {r['by']}  {r['url']}")
    elif a.cmd == "get":
        dest, meta = get(a.id, a.video, a.out); print(dest, meta["size"], meta["author"])
    else:
        print(sheet(a.query, a.out, a.orientation))


if __name__ == "__main__":
    main()
