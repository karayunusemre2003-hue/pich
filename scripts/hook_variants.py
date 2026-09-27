#!/usr/bin/env python3
"""Hook A/B/C (Faz 5): preview several hook cards, compare frame 0 side by side, pick one.

    python3 hook_variants.py plan.json variants.json --out-dir DIR            # previews + DIR/hooks.jpg
    python3 hook_variants.py plan.json variants.json --out-dir DIR --pick B   # DIR/plan.final.json

variants.json: [{"name": "A", "hook": {"eyebrow": "...", "from_text": "...", "to_text": "..."}}, ...]
Each variant overrides the plan's first `hook_card` layer (any of its keys). Previews are 540p, first 3 s
(render_reel.py --until 3); the sheet shows each hook at 0.5 s. DIR/STATE.md records variants and the pick.
Share the sheet with whoever picks the hook; nothing is sent anywhere automatically.
"""
import argparse, copy, hashlib, json, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reel_graphics as g  # noqa: E402


def rebase(plan, base):
    """Make every path-bearing field absolute so the plan still works from out-dir."""
    def fix(v):
        p = Path(v).expanduser()
        return str(p if p.is_absolute() else base / p)
    for k in ("source", "font"):
        if plan.get(k): plan[k] = fix(plan[k])
    for L in plan.get("layers", []):
        if "src" in L: L["src"] = fix(L["src"])
    aud = plan.get("audio", {})
    if aud.get("music", {}).get("file"): aud["music"]["file"] = fix(aud["music"]["file"])
    for x in aud.get("sfx", []):
        if "file" in x: x["file"] = fix(x["file"])


def apply(plan, v, build_dir):
    p = copy.deepcopy(plan)
    hooks = [L for L in p.get("layers", []) if L["kind"] == "hook_card"]
    if not hooks: sys.exit("plan has no hook_card layer to vary")
    hooks[0].update(v["hook"]); p["build_dir"] = str(build_dir)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("variants"); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--pick")
    a = ap.parse_args()
    plan_path = Path(a.plan).resolve(); plan = json.loads(plan_path.read_text())
    variants = json.loads(Path(a.variants).read_text()); out = Path(a.out_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
    names = [v["name"] for v in variants]
    if len(set(names)) != len(names): sys.exit("variant names must be unique")
    rebase(plan, plan_path.parent)
    state = out / "STATE.md"

    if a.pick:
        v = next((v for v in variants if v["name"] == a.pick), None)
        if not v: sys.exit(f"unknown variant {a.pick}; choose from {names}")
        final = apply(plan, v, out / "final-build"); fp = out / "plan.final.json"
        fp.write_text(json.dumps(final, indent=1, ensure_ascii=False))
        with state.open("a") as f: f.write(f"\n- Seçilen hook: **{a.pick}** — {v['hook']} → {fp.name}\n")
        print(f"final plan: {fp}\nrender: python3 {HERE / 'render_reel.py'} {fp} {out / 'final.mp4'}")
        return

    procs = {}
    for v in variants:  # previews render in parallel
        pp = out / f"plan_{v['name']}.json"; mp4 = out / f"preview_{v['name']}.mp4"
        txt = json.dumps(apply(plan, v, out / f"build_{v['name']}"), indent=1, ensure_ascii=False); pp.write_text(txt)
        sha = hashlib.sha256(txt.encode()).hexdigest(); ok = out / f"preview_{v['name']}.ok"
        if mp4.exists() and ok.exists() and ok.read_text() == sha: continue  # same plan, rendered successfully before
        for f in (mp4, ok, Path(str(mp4)[:-4] + ".manifest.json"), Path(str(mp4)[:-4] + ".qa.json")):
            f.unlink(missing_ok=True)  # stale or failed preview of another plan version
        procs[v["name"]] = (sha, ok), subprocess.Popen([sys.executable, str(HERE / "render_reel.py"), str(pp), str(mp4), "--preview", "--until", "3"],
                                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    errs = {n: p.communicate()[1] for n, (_, p) in procs.items()}
    bad = {n: (errs[n].strip().splitlines() or ["failed"])[-1] for n, (_, p) in procs.items() if p.returncode}
    for n, ((sha, ok), p) in procs.items():
        if not p.returncode: ok.write_text(sha)
    if bad: sys.exit("\n".join(f"variant {n}: {m}" for n, m in bad.items()))
    tiles = []
    for v in variants:
        mp4 = out / f"preview_{v['name']}.mp4"; fr = out / f"hook_{v['name']}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=360:-2", str(fr)], check=True)
        tiles.append((v["name"], Image.open(fr).convert("RGB")))
    w, h = tiles[0][1].size; sheet = Image.new("RGB", (w * len(tiles), h + 44), (20, 24, 33)); d = ImageDraw.Draw(sheet)
    for i, (n, im) in enumerate(tiles):
        sheet.paste(im, (i * w, 44)); d.text((i * w + 12, 8), f"Hook {n}", font=g.Style().font(26, 800), fill=(255, 214, 77))
    sheet.save(out / "hooks.jpg", quality=90)
    with state.open("w") as f:
        f.write(f"# Hook varyantları — {plan_path.name}\n\n" + "".join(f"- **{v['name']}**: {v['hook']} → preview_{v['name']}.mp4\n" for v in variants))
    print(f"sheet: {out / 'hooks.jpg'}  ({len(tiles)} variants)  -> pick with --pick NAME")


if __name__ == "__main__":
    main()
