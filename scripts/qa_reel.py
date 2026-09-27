#!/usr/bin/env python3
"""Automatic QA for a render_reel.py output (Faz 4). Objective checks only; a human still watches.

    python3 qa_reel.py OUT.mp4 --plan plan.json [--no-asr] [--no-faces]

Checks (FAIL blocks delivery, WARN needs a look):
  faces    FAIL  a layer's visible pixels touch the speaker's face. Faces are found with macOS Vision
                 on the *clean source frame* (same crop as the render), so a layer covering the face
                 cannot hide it from the check. During the slide the face is mapped into the PiP box.
  asr      FAIL  the rendered audio, re-transcribed, doesn't contain a caption's words around its time
  sync     FAIL  an EDL segment's voice is offset > 40 ms from the source (envelope cross-correlation)
  loudness FAIL  integrated loudness off -14 LUFS by > 1.5 LU, or true peak above -1 dBTP
  frames   FAIL  frame count / A-V length mismatch, or a black last frame; WARN no hook on frame 0
  ig_ui    WARN  a layer overlaps the *estimated* Instagram Reels UI zones (design preset)
Writes OUT.autoqa.json and OUT.autoqa.jpg (key frames: face red, layers green, IG zones grey).
"""
import argparse, difflib, json, math, re, subprocess, sys, tempfile, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_reel as rr  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from speech_map import SR, db, load_pcm  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
FACE_BIN = Path.home() / ".cache" / "jarvis-video-studio" / "face_detect"
# Vision boxes run brow->chin. Grow up for hair, a little sideways; the mouth sits at ~65% of the box height.
HAIR, SIDE, CORE = 0.25, 0.10, 0.72


# ---------------- geometry ----------------
def inter(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1]); x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)


def face_zones(f):
    """(core, full): core = hair..mouth (never cover), full = + chin (covering it is a warning)."""
    x, y, w, h = f[0] - f[2] * SIDE, f[1] - f[3] * HAIR, f[2] * (1 + 2 * SIDE), f[3] * HAIR
    return [x, y, w, h + f[3] * CORE], [x, y, w, h + f[3]]


def layer_box(L, W, H):
    """Normalized box of the layer's visible pixels (alpha bbox captured at render time), unioned over
    its whole 'rise' slide-in path (it starts `rise` px lower and moves up to y)."""
    bb = L.get("bbox")
    if bb is None and "bbox" not in L:  # old manifests: read the PNG
        with Image.open(L["path"]) as im: bb = im.convert("RGBA").split()[3].point(lambda v: 255 if v > 24 else 0).getbbox()
    if not bb: return None
    rise = max(0, L.get("rise", 0))
    return [(L["x"] + bb[0]) / W, (L["y"] + bb[1]) / H, (bb[2] - bb[0]) / W, (bb[3] - bb[1] + rise) / H]


def face_layer_conflicts(samples, layers, W, H):
    """samples: [(t, [face boxes normalized in output frame])]; returns list of conflicts."""
    out = []
    for t, faces in samples:
        for L in layers:
            if not (L["t0"] <= t <= L["t1"]): continue
            lb = layer_box(L, W, H)
            if not lb: continue
            for f in faces:
                core, full = face_zones(f)
                sev = "fail" if inter(lb, core) > 0 else "warn" if inter(lb, full) > 0 else None
                if sev: out.append({"t": round(t, 2), "severity": sev, "layer": Path(L["path"]).name, "kind": L["kind"], "face": [round(v, 3) for v in f]})
    return out


# ---------------- faces ----------------
def face_binary():
    src = SKILL / "scripts" / "face_detect.swift"
    if not FACE_BIN.exists() or FACE_BIN.stat().st_mtime < src.stat().st_mtime:
        FACE_BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(src), "-o", str(FACE_BIN)], check=True, capture_output=True)
    return FACE_BIN


def seg_at(man, t):
    for s in man["edl"]:
        d = s["src_end"] - s["src_start"]
        if s["out_start"] <= t < s["out_start"] + d: return s, s["src_start"] + (t - s["out_start"])
    return None, None


def active_window(man, t):
    """What shows the camera at t: the slide (drawn above B-roll) wins, else the last-listed B-roll (drawn on top).
    A full B-roll only hides the camera while fully opaque (between its fades)."""
    sl = man.get("slide")
    if sl and sl["t0"] <= t <= sl["t1"]: return dict(sl, mode="full_pip")
    for w in reversed(man.get("camera_windows", [])):
        if w["mode"] == "full" and w["t0"] + w.get("fade_in", 0) <= t <= w["t1"] - w.get("fade_out", 0): return w
        if w["mode"] == "full_pip" and w["t0"] <= t <= w["t1"]: return w
    return None


def hidden_intervals(man):
    """Merged intervals where the camera is fully hidden (opaque full B-roll not covered by the slide)."""
    iv = sorted((w["t0"] + w.get("fade_in", 0), w["t1"] - w.get("fade_out", 0)) for w in man.get("camera_windows", []) if w["mode"] == "full")
    sl = man.get("slide"); out = []
    for a, b in iv:
        if sl:  # the slide shows the camera in its PiP, so it cuts hidden time
            if sl["t0"] <= a and b <= sl["t1"]: continue
            if a < sl["t0"] < b: b = min(b, sl["t0"])
        if out and a <= out[-1][1]: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out


def face_samples(man, src, W, H, step=0.5):
    times = set(round(i * step, 2) for i in range(int(man["duration_s"] / step) + 1))
    for L in man["layers"]:
        for t in (L["t0"] + 0.04, (L["t0"] + L["t1"]) / 2, L["t1"] - 0.04): times.add(round(t, 2))
    for w in man.get("camera_windows", []):  # B-roll fades: the camera is still visible underneath
        for t in (w["t0"] + 0.02, w["t1"] - 0.02): times.add(round(t, 2))
    times = sorted(t for t in times if 0 <= t < man["duration_s"])
    tmp = Path(tempfile.mkdtemp()); jobs = []
    for i, t in enumerate(times):
        s, st = seg_at(man, t)
        if not s: continue
        cw, ch, cx, cy = s["crop"]; p = tmp / f"f{i:04d}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{st:.3f}", "-i", str(src), "-frames:v", "1",
                        "-vf", f"crop={cw}:{ch}:{cx}:{cy},scale={W // 2}:{H // 2}", str(p)], check=True)
        jobs.append((t, p))
    res = json.loads(subprocess.check_output([str(face_binary())] + [str(p) for _, p in jobs]))
    out = []
    for t, p in jobs:
        faces = res.get(str(p), [])
        win = active_window(man, t)
        if win and win["mode"] == "full":  # camera hidden behind an opaque full-frame B-roll
            faces = []
        elif win:  # camera only visible through the PiP window
            (bx, by, bw, bh), (px, py, pw, ph) = win["pip_box"], win["pip_crop"]
            mapped = []
            for f in faces:  # map through the PiP crop, then clip to the PiP window (outside it the face isn't shown)
                fx0, fy0, fx1, fy1 = f[0] * W, f[1] * H, (f[0] + f[2]) * W, (f[1] + f[3]) * H
                fx0, fy0, fx1, fy1 = max(fx0, px), max(fy0, py), min(fx1, px + pw), min(fy1, py + ph)
                if fx1 <= fx0 or fy1 <= fy0: continue
                mapped.append([(bx + (fx0 - px) * bw / pw) / W, (by + (fy0 - py) * bh / ph) / H, (fx1 - fx0) * bw / pw / W, (fy1 - fy0) * bh / ph / H])
            faces = mapped
        out.append((t, faces))
    return out


# ---------------- audio ----------------
def env(d, a, b, step=0.01):
    return [db(d, a + i * step, a + (i + 1) * step) for i in range(int((b - a) / step))]


def best_lag(x, y, max_lag=20):
    """lag (in steps) maximizing correlation of y against x; positive = output late."""
    def corr(k):
        pairs = [(x[i], y[i + k]) for i in range(len(x)) if 0 <= i + k < len(y)]
        if len(pairs) < 10: return -1
        mx = sum(p[0] for p in pairs) / len(pairs); my = sum(p[1] for p in pairs) / len(pairs)
        num = sum((p[0] - mx) * (p[1] - my) for p in pairs)
        den = math.sqrt(sum((p[0] - mx) ** 2 for p in pairs) * sum((p[1] - my) ** 2 for p in pairs)) or 1
        return num / den
    scores = {k: corr(k) for k in range(-max_lag, max_lag + 1)}
    top = max(scores.values())
    k = min((k for k, v in scores.items() if v >= top - 0.005), key=abs)  # ties -> smallest shift
    return k, round(scores[k], 3)


def sync_check(man, src_pcm, out_pcm):
    rows = []
    for i, s in enumerate(man["edl"]):
        d = min(s["src_end"] - s["src_start"], man["duration_s"] - s["out_start"])  # --until outputs are shorter
        if d < 0.5: continue
        x = env(src_pcm, s["src_start"], s["src_start"] + d); y = env(out_pcm, s["out_start"], s["out_start"] + d)
        mx = sum(x) / len(x); sd = math.sqrt(sum((v - mx) ** 2 for v in x) / len(x))
        if max(x) < -45 or sd < 3: continue  # silent / flat segment: nothing to align
        k, c = best_lag(x, y)
        ok = c >= 0.5  # weak correlation = can't tell (warn), not proof of offset
        rows.append({"seg": i, "lag_ms": k * 10, "corr": c, "conclusive": ok, "pass": (not ok) or abs(k * 10) <= 40})
    return rows


def norm_words(t):
    t = t.replace("I", "ı").replace("İ", "i").lower().translate(str.maketrans("âîû", "aiu"))  # Turkish casing
    return [w[:5] for w in re.findall(r"[\wçğıöşü]+", t) if w]  # 5-char stems absorb suffix/ASR spelling drift


def voice_stem(man, dest):
    """The render's voice timeline without music/SFX: the same EDL trims from the source, concatenated."""
    segs = [s for s in man["edl"] if s["out_start"] < man["duration_s"]]
    parts = "".join(f"[0:a]atrim=start={s['src_start']:.4f}:end={s['src_end']:.4f},asetpts=PTS-STARTPTS"
                    + (f",volume={s['volume']}" if s.get("volume") is not None else "") + f"[a{i}];" for i, s in enumerate(segs))
    graph = parts + "".join(f"[a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1,atrim=end={man['duration_s']:.4f}[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", man["source"], "-filter_complex", graph, "-map", "[o]", "-ac", "1", "-ar", str(SR),
                    "-c:a", "pcm_s16le", str(dest)], check=True)


def asr_check(man, out_path):
    """Captions vs speech on the voice stem (FAIL basis); the mixed render only flags music masking (WARN)."""
    import transcribe as tr
    tmp = Path(tempfile.mkdtemp()); stem, mix = tmp / "voice.wav", tmp / "mix.wav"
    voice_stem(man, stem)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out_path), "-map", "0:a", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(mix)], check=True)
    models = [m for m in (tr.DEFAULT_MODEL, tr.SECOND_MODEL) if Path(m).exists()]  # a caption counts as heard if either model hears it
    runs = {k: [tr.whisper_words(w, m, "tr") for m in models] for k, w in (("voice", stem), ("mix", mix))}

    def score(c, passes):
        cap = norm_words(c["text"]); best = (-1, "")
        for words in passes:
            near = [w for x in words if c["t0"] - 0.4 <= (x["start"] + x["end"]) / 2 <= c["t1"] + 0.4 for w in norm_words(x["w"])]
            hit = sum(b.size for b in difflib.SequenceMatcher(a=cap, b=near, autojunk=False).get_matching_blocks())  # ordered
            best = max(best, (round(hit / max(1, len(cap)), 2), " ".join(near)))
        return best
    rows = []
    for c in (o for o in man["overlays"] if o.get("kind") == "caption"):
        (r, heard), (rm, heard_m) = score(c, runs["voice"]), score(c, runs["mix"])
        rows.append({"text": c["text"], "t0": round(c["t0"], 2), "match": r, "heard": heard, "match_mix": rm, "heard_mix": heard_m,
                     "pass": r >= 0.5, "warn": r < 0.8, "masked": r - rm >= 0.34})
    return rows, " ".join(w["w"] for w in runs["mix"][0])


# ---------------- report ----------------
def contact(out_path, man, samples, W, H, path):
    inner = sorted(set([round((L["t0"] + L["t1"]) / 2, 2) for L in man["layers"] if L["kind"] != "caption"]
                       + [round(t + 0.1, 2) for t in (man.get("slide") or {}).get("steps", [])]))
    inner = [t for t in inner if 0.05 < t < man["duration_s"] - 0.1]
    if len(inner) > 6: inner = [inner[round(i * (len(inner) - 1) / 5)] for i in range(6)]
    keys = [0.0] + inner + [max(0.0, man["duration_s"] - 1 / man["fps"])]  # first and final frame always shown
    tw, th = W // 4, H // 4; sheet = Image.new("RGB", (tw * len(keys), th), (0, 0, 0))
    for i, t in enumerate(keys):
        fp = Path(tempfile.mkdtemp()) / "k.png"
        seek = ["-sseof", "-0.5"] if i == len(keys) - 1 else ["-ss", f"{t:.3f}"]  # exact seeks to the final frame can return nothing
        subprocess.run(["ffmpeg", "-v", "error", "-y", *seek, "-i", str(out_path), "-vf", f"scale={tw}:{th}", "-update", "1", *([] if i == len(keys) - 1 else ["-frames:v", "1"]), str(fp)], check=True)
        im = Image.open(fp).convert("RGBA"); ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        box = lambda b: [b[0] * tw, b[1] * th, (b[0] + b[2]) * tw, (b[1] + b[3]) * th]
        for z in man.get("ig_ui_estimate", {}).values(): d.rectangle(box(z), fill=(128, 128, 128, 70))
        for L in man["layers"]:
            if L["t0"] <= t <= L["t1"] and (lb := layer_box(L, W, H)): d.rectangle(box(lb), outline=(0, 255, 120, 255), width=2)
        near = min(samples, key=lambda s: abs(s[0] - t)) if samples else (t, [])
        for f in near[1]:
            core, full = face_zones(f)
            d.rectangle(box(full), outline=(255, 170, 40, 255), width=1); d.rectangle(box(core), outline=(255, 40, 40, 255), width=2)
        d.text((4, 4), f"{t:.2f}s", fill=(255, 255, 255, 255))
        sheet.paste(Image.alpha_composite(im, ov).convert("RGB"), (i * tw, 0))
    sheet.save(path, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--plan", required=True)
    ap.add_argument("--no-asr", action="store_true"); ap.add_argument("--no-faces", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); plan_path = Path(a.plan).resolve(); plan = json.loads(plan_path.read_text())
    mp = Path(str(out)[:-4] + ".manifest.json")  # written by render_reel.py next to *this* output
    if not mp.exists(): sys.exit(f"{mp.name} missing: render this file with render_reel.py (0.5.1+) first")
    man = json.loads(mp.read_text())
    if Path(man["output"]) != out.resolve(): sys.exit(f"{mp.name} belongs to {man['output']}, not {out}")
    src = Path(man["source"]); W, H = man.get("width", 1080), man.get("height", 1920)  # the file actually rendered (proxy for previews)
    fails, warns, rep = [], [], {"file": str(out)}

    base = rr.basic_qa(out, man["total_frames"], man["fps"]); rep["basic"] = base
    if not all(base["checks"].values()): fails.append("frames/av")
    li, tp = base["lufs_i"], base["true_peak_dbfs"]
    rep["loudness"] = {"lufs_i": li, "true_peak": tp, "pass": li is not None and abs(li + 14) <= 1.5 and tp is not None and tp <= -1.0}
    if not rep["loudness"]["pass"]: fails.append("loudness")

    lf = Path(tempfile.mkdtemp()) / "last.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.5", "-i", str(out), "-vf", "scale=64:-2,format=gray", "-update", "1", str(lf)], check=True)  # keeps the very last frame
    with Image.open(lf) as im: luma = sum(im.tobytes()) / (im.width * im.height)
    rep["last_frame_luma"] = round(luma, 1)
    if luma < 12: fails.append("black last frame")
    if not any(L["kind"] == "hook_card" and L["t0"] <= 0.001 and not L.get("fade_in") for L in man["layers"]):
        warns.append("no fully visible hook card on frame 0")

    zones = man.get("ig_ui_estimate", {}); ui = []
    for L in man["layers"]:
        lb = layer_box(L, W, H)
        for zn, z in zones.items():
            if lb and inter(lb, z) > 0.002: ui.append({"layer": Path(L["path"]).name, "zone": zn})
    rep["ig_ui"] = ui
    if ui: warns.append(f"{len(ui)} layer/IG-UI overlaps (estimate)")

    src_pcm, out_pcm = load_pcm(src), load_pcm(out)
    rep["sync"] = sync_check(man, src_pcm, out_pcm)
    if not all(r["pass"] for r in rep["sync"]): fails.append("sync")
    if not all(r["conclusive"] for r in rep["sync"]): warns.append("sync inconclusive for some segments (weak correlation)")

    samples = []
    if not a.no_faces and sys.platform != "darwin":
        warns.append("face check skipped: needs macOS Vision (use --no-faces on Linux and check faces by eye)")
    elif not a.no_faces:
        samples = face_samples(man, src, W, H)
        rep["faces"] = {"samples": len(samples), "with_face": sum(1 for _, f in samples if f),
                        "conflicts": face_layer_conflicts(samples, man["layers"], W, H)}
        sev = [c["severity"] for c in rep["faces"]["conflicts"]]
        if "fail" in sev: fails.append("layer covers face (eyes/mouth)")
        elif sev: warns.append(f"layer touches chin ({len(sev)} samples)")
        hidden = hidden_intervals(man)

        def seen(L):  # how long the layer is visible while the camera is on screen (merged intervals: no double count)
            return (L["t1"] - L["t0"]) - sum(max(0.0, min(L["t1"], b) - max(L["t0"], a)) for a, b in hidden)
        blind = [Path(L["path"]).name for L in man["layers"]
                 if seen(L) >= 0.3 and not any(f for t, f in samples if L["t0"] <= t <= L["t1"] and not any(a <= t <= b for a, b in hidden))]
        rep["faces"]["layers_without_face_samples"] = blind
        if blind: warns.append(f"no face detected while {len(blind)} layer(s) visible - check those by eye")
    if not a.no_asr:
        rows, heard = asr_check(man, out)
        rep["asr"] = {"captions": rows, "heard": heard}
        if not all(r["pass"] for r in rows): fails.append("caption/ASR mismatch")
        if any(r["warn"] for r in rows): warns.append("some captions only partly heard")
        masked = [r["text"] for r in rows if r["masked"]]
        if masked: warns.append(f"music may mask speech under {len(masked)} caption(s): {masked[:3]} — lower music gain there or check by ear")

    rep["status"] = "FAIL" if fails else "AUTO_PASS"; rep["fails"] = fails; rep["warns"] = warns
    rep["human_review_required"] = True
    j = Path(str(out)[:-4] + ".autoqa.json"); j.write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    contact(out, man, samples, W, H, Path(str(out)[:-4] + ".autoqa.jpg"))
    print(f"{rep['status']}  fails={fails}  warns={warns}  -> {j}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
