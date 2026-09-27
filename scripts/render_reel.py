#!/usr/bin/env python3
"""Plan-driven single-pass Reel renderer.

    python3 render_reel.py plan.json out.mp4 [--preview] [--graph-only]

One ffmpeg pass: EDL trims (+ per-segment zoom crop) -> concat -> stepper slide + PiP ->
source-timed overlays (hook, image cards, badge, wordmark, CTA, captions) -> tv-range yuv420p.
Audio: voice chain + ducked music (sidechain) + SFX -> loudnorm. Every overlay time is anchored
to *source seconds inside an EDL segment*, so changing the EDL never slides a layer off its words.
Assets are built into <plan dir>/build/. Refuses to overwrite. Output QA stays REVIEW.
See references/render-reel-plan.md for the plan schema.
"""
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reel_graphics as g  # noqa: E402
import iconify  # noqa: E402

VOICE_CHAIN = "highpass=f=75,acompressor=threshold=-24dB:ratio=2.5:attack=8:release=120:makeup=2,aformat=channel_layouts=stereo"


class Timeline:
    def __init__(self, edl, fps):
        self.fps = fps
        self.segs = [(round(s["start"] * fps), round(s["end"] * fps)) for s in edl]
        self.offs, acc = [], 0
        for a, b in self.segs:
            if b <= a: raise ValueError(f"empty/negative EDL segment {a}-{b}")
            self.offs.append(acc); acc += b - a
        self.total = acc
        self.dur = acc / fps
        self.slide = None

    def o(self, src_t, seg):
        """source seconds inside segment seg -> output seconds (clamped to the segment)"""
        a, b = self.segs[seg]
        f = min(max(round(src_t * self.fps), a), b)
        return (self.offs[seg] + f - a) / self.fps

    def bounds(self, seg):
        return self.offs[seg] / self.fps, (self.offs[seg] + self.segs[seg][1] - self.segs[seg][0]) / self.fps

    def t(self, ref):
        """ref: 'start' | 'end' | number (output s) | {seg, t: src_s|'start'|'end', offset} | {slide: start|end, offset}"""
        if ref == "start": return 0.0
        if ref == "end": return self.dur
        if isinstance(ref, (int, float)): return float(ref)
        off = ref.get("offset", 0)
        if "slide" in ref:
            v = self.slide[0] if ref["slide"] == "start" else self.slide[1]
        else:
            seg, st = ref["seg"], ref.get("t", "start")
            if st == "start": v = self.bounds(seg)[0]
            elif st == "end": v = self.bounds(seg)[1]
            else: v = self.o(st, seg)
        return v + off if off else v


def rel(base, p):
    p = Path(os.path.expanduser(p))
    return p if p.is_absolute() else (base / p)


def synth_music_pad(path, dur):
    """Original two-chord pad (Am9 <-> Fmaj7); no third-party audio."""
    ch1 = [220.0, 261.63, 329.63, 392.0, 493.88]; ch2 = [174.61, 220.0, 261.63, 329.63, 440.0]
    chord = lambda fs, det: "+".join(f"sin(2*PI*{f*det:.3f}*t)" for f in fs)
    w = "(0.5+0.5*cos(2*PI*t/8))"; pulse = "(0.82+0.18*(0.5+0.5*cos(2*PI*4*t)))"
    env = f"min(1,t/1.2)*min(1,({dur}-t)/1.6)"
    L = f"0.05*({w}*({chord(ch1,1)})+(1-{w})*({chord(ch2,1)}))*{pulse}*{env}"
    R = f"0.05*({w}*({chord(ch1,1.003)})+(1-{w})*({chord(ch2,1.003)}))*{pulse}*{env}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "aevalsrc=" + (L + "|" + R).replace(",", "\\,") + f":s=48000:d={dur}",
                    "-af", "lowpass=f=1600,aecho=0.8:0.7:120|260:0.25|0.18,volume=1.0", str(path)], check=True)


SYNTH_SFX = {
    "whoosh": ["anoisesrc=d=0.55:c=pink:r=48000:a=0.5:seed=1",
               "highpass=f=500,lowpass=f=6000,afade=t=in:d=0.35:curve=exp,afade=t=out:st=0.35:d=0.2,aformat=channel_layouts=stereo"],
    "chime": ["aevalsrc=0.25*sin(2*PI*659.25*t)*exp(-5*t)+0.22*gte(t\\,0.11)*sin(2*PI*987.77*(t-0.11))*exp(-5*(t-0.11)):s=48000:d=1.2",
              "aformat=channel_layouts=stereo"],
}


def synth_sfx(name, path):
    src, af = SYNTH_SFX[name]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-af", af, str(path)], check=True)


PROXY_DIR = Path.home() / ".cache" / "jarvis-video-studio" / "proxy"


def make_proxy(src, w, h):
    """Half-res, short-GOP H.264 copy of the source (same fps, range and audio), cached by path+size+mtime."""
    st = Path(src).stat()
    key = hashlib.sha256(f"{Path(src).resolve()}|{st.st_size}|{st.st_mtime_ns}|{w}x{h}".encode()).hexdigest()[:16]
    out = PROXY_DIR / f"{Path(src).stem}-{key}.mp4"
    if not out.exists():
        PROXY_DIR.mkdir(parents=True, exist_ok=True); part = out.with_suffix(".part.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0", "-vf", f"scale={w}:{h}:flags=bicubic",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "15", "-c:a", "copy", str(part)], check=True)
        part.rename(out)
    return out


def load_design(name):
    p = g.SKILL_DIR / "assets" / "design" / f"{name}.json"
    if not p.exists(): raise ValueError(f"unknown design preset {name!r}")
    return json.loads(p.read_text())


def logo_png(key, height, out):
    """Verified logo from assets/logos/manifest.json, scaled to `height` px (keeps aspect)."""
    d = Path(os.environ.get("JVS_LOGOS_DIR", g.SKILL_DIR / "assets" / "logos")).expanduser().resolve()
    man = json.loads((d / "manifest.json").read_text())["logos"]
    e = man.get(key)
    if not e or not all(e.get(k) for k in ("file", "source_url", "verified_at")):
        raise ValueError(f"logo {key!r} not in the verified library (needs file, source_url, verified_at)")
    f = (d / e["file"]).resolve()
    if d not in f.parents or not f.is_file(): raise ValueError(f"logo {key!r}: file must exist inside the logo library ({d})")
    with g.Image.open(f) as im:
        im = im.convert("RGBA"); w = round(im.width * height / im.height)
        im.resize((w, height), g.Image.LANCZOS).save(out)
    return out, (w, height)


def video_geometry(path):
    """Displayed width/height (rotation + sample aspect ratio applied) and the *video stream* duration."""
    st = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height,sample_aspect_ratio,duration,duration_ts,time_base,nb_frames,avg_frame_rate:stream_side_data=rotation",
                                             "-of", "json", str(path)]))["streams"][0]
    w, h = st["width"], st["height"]
    sar = st.get("sample_aspect_ratio") or "1:1"
    if ":" in sar and not sar.startswith("0"):
        n, d = map(int, sar.split(":")); w = round(w * n / d)
    rot = next((abs(int(float(sd.get("rotation", 0)))) for sd in st.get("side_data_list", []) if "rotation" in sd), 0)
    if rot % 180 == 90: w, h = h, w
    dur = st.get("duration")
    if dur in (None, "N/A"):
        tb = st.get("time_base", "1/1").split("/"); dts = st.get("duration_ts")
        dur = int(dts) * int(tb[0]) / int(tb[1]) if dts else 0.0
    return w, h, float(dur)


def _num(v, name, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not (lo <= v <= hi):
        raise ValueError(f"{name} must be a number in [{lo}, {hi}], got {v!r}")


def validate(plan):
    """Reject unsafe/unsupported plans before any asset or ffmpeg work (values go into the filter graph)."""
    if (plan.get("width", 1080), plan.get("height", 1920)) != (1080, 1920):
        raise ValueError("v0.4 templates are laid out for 1080x1920 only")
    if plan.get("source_range", "pc") not in ("pc", "tv"): raise ValueError("source_range must be 'pc' or 'tv'")
    if not isinstance(plan.get("fps", 30), int): raise ValueError("fps must be an integer")
    for i, s in enumerate(plan["edl"]):
        _num(s["start"], f"edl[{i}].start", 0, 1e6); _num(s["end"], f"edl[{i}].end", 0, 1e6)
        _num(s.get("zoom", 1.0), f"edl[{i}].zoom", 1.0, 4.0)
        if s.get("volume") is not None: _num(s["volume"], f"edl[{i}].volume", 0, 4)
    aud = plan.get("audio", {}); mus = aud.get("music")
    if mus:
        _num(mus.get("gain_db", -17), "music.gain_db", -60, 0)
        if mus.get("synth") not in (None, "pad"): raise ValueError("music.synth must be 'pad'")
        if "synth" not in mus and mus.get("rights_checked") is not True:
            raise ValueError("music.rights_checked must be true (see audio-license-ledger)")
    for j, x in enumerate(aud.get("sfx", [])):
        _num(x["gain_db"], f"sfx[{j}].gain_db", -60, 0)
        if "synth" in x and x["synth"] not in SYNTH_SFX: raise ValueError(f"sfx[{j}].synth must be one of {list(SYNTH_SFX)}")
        if "synth" not in x and x.get("rights_checked") is not True: raise ValueError(f"sfx[{j}] needs rights_checked: true")
    ln = aud.get("loudnorm", {"I": -14, "TP": -1.5, "LRA": 9})
    _num(ln["I"], "loudnorm.I", -40, -5); _num(ln["TP"], "loudnorm.TP", -9, 0); _num(ln["LRA"], "loudnorm.LRA", 1, 20)
    for i, L in enumerate(plan.get("layers", [])):
        if L.get("kind") == "icon":
            iconify.check_name(L.get("icon"))
            if "card" in L and not isinstance(L["card"], bool): raise ValueError(f"layers[{i}].card must be true/false")
            c = L.get("color", "yellow")
            if c is not None and not (isinstance(c, str) and (c in g.DEFAULT_TOKENS or c in plan.get("tokens", {}) or re.fullmatch(r"[0-9A-Fa-f]{6}", c))):
                raise ValueError(f"layers[{i}].color must be null, a token name or RRGGBB")
            if not isinstance(L.get("size", 120), int) or not 16 <= L.get("size", 120) <= 800: raise ValueError(f"layers[{i}].size must be an integer 16..800")
        if L.get("kind") == "broll":
            if L.get("mode", "full") not in ("full", "full_pip", "card"): raise ValueError(f"layers[{i}].mode must be full, full_pip or card")
            _num(L.get("src_start", 0), f"layers[{i}].src_start", 0, 1e5)
            if L.get("mode") == "card": _num(L.get("width", 600), f"layers[{i}].width", 200, 1080)
        if L.get("kind") == "cta_card" and len(L.get("lines", [])) != 2: raise ValueError(f"layers[{i}].lines: CTA needs exactly 2 lines")
        if "logo" in L and (not isinstance(L.get("height", 96), int) or not 16 <= L.get("height", 96) <= 600):
            raise ValueError(f"layers[{i}].height must be an integer 16..600")
        for k in ("y", "fade_in", "fade_out", "rise"):
            if k in L: _num(L[k], f"layers[{i}].{k}", -2000, 4000)
        if L.get("x", "center") != "center": _num(L["x"], f"layers[{i}].x", -2000, 4000)


def source_fps(src):
    st = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=r_frame_rate,avg_frame_rate", "-of", "json", str(src)]))["streams"][0]
    frac = lambda v: (lambda n, d: n / d if d else 0)(*map(int, v.split("/")))
    return frac(st["r_frame_rate"]), frac(st["avg_frame_rate"])


def build(plan_path, out_path, preview=False, graph_only=False, until=None):
    plan_path = Path(plan_path).resolve(); base = plan_path.parent
    plan = json.loads(plan_path.read_text())
    try: validate(plan); load_design(plan.get("design", "default"))
    except (ValueError, KeyError) as e: sys.exit(f"invalid plan: {e}")
    W, H, FPS = plan.get("width", 1080), plan.get("height", 1920), plan.get("fps", 30)
    SW, SH = plan.get("source_size", [2160, 3840]); ay = plan.get("crop_anchor_y", 0.28)
    src = rel(base, plan["source"])
    B = rel(base, plan.get("build_dir", "build")); B.mkdir(parents=True, exist_ok=True)
    work = B / "work"; work.mkdir(exist_ok=True)
    out_path = Path(out_path)
    if out_path.exists() and not graph_only: sys.exit(f"refuse to overwrite {out_path}")
    if not graph_only:  # trim=start_frame counts source frames: source must be CFR at the plan fps
        r, avg = source_fps(src)
        if abs(r - FPS) > 0.01 or abs(avg - FPS) > 0.05:
            sys.exit(f"source is {r:.3f} fps (avg {avg:.3f}), plan fps {FPS}: conform the source to CFR {FPS} first")
        if preview and SW > 1080:  # previews trim from a cached half-res proxy instead of decoding 4K from 0 s
            src = make_proxy(src, SW // 2 // 2 * 2, SH // 2 // 2 * 2); SW, SH = SW // 2 // 2 * 2, SH // 2 // 2 * 2
    design = load_design(plan.get("design", "default"))
    tokens = dict(design.get("tokens", {}), **plan.get("tokens", {}))
    font = rel(base, plan["font"]) if plan.get("font") else g.SKILL_DIR / "assets" / design.get("font", "fonts/Manrope.ttf")
    st = g.Style(tokens, font, W, H)
    edl = plan["edl"]; tl = Timeline(edl, FPS); dur = tl.dur

    manifest = {"source": str(src), "fps": FPS, "total_frames": tl.total, "duration_s": dur, "width": W, "height": H,
                "zones": design.get("zones", {}), "ig_ui_estimate": design.get("ig_ui_estimate", {}), "edl": [], "overlays": [], "layers": []}
    for s, (a, b), off in zip(edl, tl.segs, tl.offs):
        z = s.get("zoom", 1.0); cw, chh = int(SW / z) // 2 * 2, int(SH / z) // 2 * 2
        manifest["edl"].append({"src_start": a / FPS, "src_end": b / FPS, "zoom": z, "out_start": off / FPS, "label": s.get("label", ""),
                                "crop": [cw, chh, (SW - cw) // 2, int(ay * SH - ay * chh) // 2 * 2], "volume": s.get("volume")})

    # ---- slide (full-frame stepper + PiP) ----
    slide = plan.get("slide"); slide_layers = []; pip = None
    if slide:
        pip = slide["pip"]["box"]
        tl.slide = (tl.t(slide["start"]), tl.t(slide["end"]))
        steps = slide["steps"]
        sl_paths = [B / f"step{i}.png" for i in range(len(steps))]
        g.stepper_slides(st, sl_paths, slide["eyebrow"], slide["title"], [(s["icon"], s["label"]) for s in steps], pip)
        step_t = [tl.t(s["at"]) for s in steps]
        sa, sb = tl.slide
        for i, pth in enumerate(sl_paths):
            last = i == len(steps) - 1
            t0 = step_t[i]; t1 = sb if last else step_t[i + 1] + slide.get("step_overlap", 0.15)
            slide_layers.append((pth, t0, t1, slide.get("fade", 0.2) if i == 0 else slide.get("step_fade", 0.12), slide.get("fade", 0.2) if last else 0))
        manifest["slide"] = {"t0": sa, "t1": sb, "steps": [round(t, 3) for t in step_t], "pip_box": pip, "pip_crop": slide["pip"]["crop"]}

    # ---- layers ----
    overlays = []  # (png, x, y, t0, t1, fade_in, fade_out, rise)
    brolls = []
    for i, L in enumerate(plan.get("layers", [])):
        kind = L["kind"]; p = B / f"layer{i:02d}_{kind}.png"
        if kind == "broll":
            vs = rel(base, L["src"])
            if not vs.exists(): raise ValueError(f"layers[{i}]: broll file not found: {vs}")
            bw, bh, vdur = video_geometry(vs)
            b = {"i": i, "src": vs, "mode": L.get("mode", "full"), "t0": tl.t(L["from"]), "t1": tl.t(L["to"]), "src_start": float(L.get("src_start", 0)),
                 "fade_in": L.get("fade_in", 0.15), "fade_out": L.get("fade_out", 0.15), "src_dur": vdur}
            if b["t1"] <= b["t0"]: raise ValueError(f"layers[{i}]: broll window is empty or reversed")
            if not (0 <= b["fade_in"] and 0 <= b["fade_out"] and b["fade_in"] + b["fade_out"] <= b["t1"] - b["t0"]):
                raise ValueError(f"layers[{i}]: fades must be >= 0 and fit inside the window")
            if b["t1"] - b["t0"] > b["src_dur"] - b["src_start"] + 0.05:
                raise ValueError(f"layers[{i}]: broll window {b['t1'] - b['t0']:.2f}s is longer than the clip after src_start")
            if b["mode"] == "card":
                w_ = int(L.get("width", 600)) // 2 * 2; h_ = int(round(w_ * bh / bw)) // 2 * 2
                b.update(w=w_, h=h_, x=(W - w_) // 2 if L.get("x", "center") == "center" else L["x"], y=L["y"], radius=L.get("radius", 34))
            else:
                pipd = L.get("pip") or (slide["pip"] if slide else {"box": [584, 540, 440, 600], "crop": [228, 770, 560, 764]})
                b.update(pip=pipd if b["mode"] == "full_pip" else None)
            brolls.append(b)
            manifest["overlays"].append({"kind": "broll", "mode": b["mode"], "src": str(vs), "t0": b["t0"], "t1": b["t1"],
                                         **({"provenance": json.loads(Path(str(vs) + ".json").read_text())} if Path(str(vs) + ".json").exists() else {})})
            continue
        if kind == "hook_card": sz, pad = g.hook_card(st, p, L["eyebrow"], L["from_text"], L["to_text"])
        elif kind == "image_card": sz, pad = g.image_card(st, rel(base, L["src"]), p, L["width"])
        elif kind == "round_badge": sz, pad = g.round_badge(st, rel(base, L["src"]), p, L["size"])
        elif kind == "wordmark": sz, pad = g.wordmark(st, p, L["text"])
        elif kind == "cta_card": sz, pad = g.cta_card(st, p, L["lines"], L["pill"])
        elif kind == "icon":
            col = L.get("color", "yellow")
            hexc = None if col is None else ("%02X%02X%02X" % st.c[col] if col in st.c else col)
            raw = B / f"layer{i:02d}_iconsrc.png" if L.get("card") else p
            ip, sz, prov = iconify.icon_png(L["icon"], raw, L.get("size", 120), hexc); pad = 0
            if L.get("card"): sz, pad = g.icon_card(st, ip, p)
            else: p = ip
            manifest["overlays"].append(dict(prov, kind="icon"))
        elif kind == "png" and "logo" in L: p, sz = logo_png(L["logo"], L.get("height", 96), B / f"layer{i:02d}_logo.png"); pad = 0
        elif kind == "png": p = rel(base, L["src"]); sz = tuple(L["size"]); pad = 0
        else: raise ValueError(f"unknown layer kind {kind}")
        x = (W - sz[0]) // 2 if L.get("x", "center") == "center" else L["x"]
        overlays.append((p, x, L["y"] - pad, tl.t(L["from"]), tl.t(L["to"]), L.get("fade_in", 0), L.get("fade_out", 0), L.get("rise", 0)))
        if kind in ("image_card", "round_badge"):
            manifest["overlays"].append({"kind": L.get("provenance", "image"), "src": str(rel(base, L["src"]))})

    # ---- captions (hard cuts; short silences bridged so captions don't blink) ----
    caps = plan.get("captions", {}); items = caps.get("items", [])
    cap_cy = int(caps.get("y", 0.728) * H)
    cap_times = [(tl.o(c["start"], c["seg"]), tl.o(c["end"], c["seg"])) for c in items]
    bridge = caps.get("bridge_gap_s", 0.35)
    for i in range(len(cap_times) - 1):
        if 0 < cap_times[i + 1][0] - cap_times[i][1] < bridge:
            cap_times[i] = (cap_times[i][0], cap_times[i + 1][0])
    for i, c in enumerate(items):
        ch = g.caption_png(st, c["text"], c.get("hl", []), p := B / f"cap{i:02d}.png")
        t0, t1 = cap_times[i]
        cy_ = int(c["y"] * H) if "y" in c else cap_cy  # per-caption override (e.g. move captions off a slide)
        overlays.append((p, 0, cy_ - ch // 2, t0, t1, 0, 0, 0))
        manifest["overlays"].append({"kind": "caption", "text": c["text"], "t0": t0, "t1": t1})

    # ---- audio assets ----
    aud = plan.get("audio", {})
    mus = aud.get("music")
    if mus:
        if mus.get("synth") == "pad":
            mus_file = B / "music_pad.wav"
            synth_music_pad(mus_file, dur)
        else:
            mus_file = rel(base, mus["file"])
    sfx_list = []
    for s in aud.get("sfx", []):
        if "synth" in s:
            f = B / f"sfx_{s['synth']}.wav"
            if not f.exists(): synth_sfx(s["synth"], f)
        else:
            f = rel(base, s["file"])
        sfx_list.append((f, tl.t(s["at"]), s["gain_db"], s.get("synth", Path(s.get("file", "")).stem)))

    # ---- filter graph ----
    inputs = ["-i", str(src)]; fc = []; vparts, aparts = [], []
    for i, (s, (a, b)) in enumerate(zip(edl, tl.segs)):
        sa_, sb_ = a / FPS, b / FPS
        cw, chh, cx, cy = manifest["edl"][i]["crop"]
        fc.append(f"[0:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,crop={cw}:{chh}:{cx}:{cy},scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}[v{i}]")
        fade_af = f"afade=t=in:d=0.012,afade=t=out:st={(b-a)/FPS-0.012:.4f}:d=0.012"
        vol = f",volume={s['volume']}" if s.get("volume") is not None else ""
        fc.append(f"[0:a]atrim=start={sa_:.4f}:end={sb_:.4f},asetpts=PTS-STARTPTS,aresample=48000,{fade_af}{vol}[a{i}]")
        vparts.append(f"[v{i}]"); aparts.append(f"[a{i}]")
    fc.append("".join(v + a for v, a in zip(vparts, aparts)) + f"concat=n={len(edl)}:v=1:a=1[vcat][acat]")
    idx = 1

    def add_input(args):
        nonlocal idx
        inputs.extend(str(x) for x in args); idx += 1; return idx - 1

    cur = "vcat"
    bpip = [b for b in brolls if b["mode"] == "full_pip"]
    pipsrcs = (["vpipsrc"] if slide else []) + [f"vpipb{j}" for j in range(len(bpip))]
    if pipsrcs:  # one camera copy per PiP consumer (a slide alone keeps the plain split line)
        fc.append("[vcat]split" + ("" if len(pipsrcs) == 1 else f"={1 + len(pipsrcs)}") + "[vbase]" + "".join(f"[{n}]" for n in pipsrcs)); cur = "vbase"
    manifest["camera_windows"] = []
    for j, b in enumerate(brolls):  # video cutaways / cards, under slide, cards and captions
        t0, t1 = b["t0"], b["t1"]; d_ = t1 - t0
        k = add_input(["-ss", f"{b['src_start']:.3f}", "-t", f"{d_ + 0.2:.3f}", "-i", b["src"]])
        tw, th = (b["w"], b["h"]) if b["mode"] == "card" else (W, H)
        fade = (f",fade=t=in:st=0:d={b['fade_in']}:alpha=1" if b["fade_in"] else "") + (f",fade=t=out:st={d_ - b['fade_out']:.3f}:d={b['fade_out']}:alpha=1" if b["fade_out"] else "")
        chain = f"[{k}:v]fps={FPS},scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},setsar=1,format=rgba"
        if b["mode"] == "card":
            mp = B / f"broll{j}_mask.png"; g.pip_mask(mp, tw, th, b["radius"])
            km = add_input(["-loop", "1", "-framerate", str(FPS), "-t", f"{d_ + 0.2:.3f}", "-i", mp])
            fc.append(f"{chain}[bvr{j}];[{km}:v]format=gray,scale={tw}:{th}[bm{j}];[bvr{j}][bm{j}]alphamerge{fade},setpts=PTS-STARTPTS+{t0:.4f}/TB[bv{j}]")
            x, y = b["x"], b["y"]
        else:
            fc.append(f"{chain}{fade},setpts=PTS-STARTPTS+{t0:.4f}/TB[bv{j}]"); x = y = 0
        fc.append(f"[{cur}][bv{j}]overlay={x}:{y}:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[cb{j}]"); cur = f"cb{j}"
        if b["mode"] == "card":
            fp = B / f"broll{j}_frame.png"; fsz, fpad = g.video_frame(fp, tw, th, b["radius"], st.c["teal"])
            kf = add_input(["-loop", "1", "-framerate", str(FPS), "-t", f"{d_ + 0.1:.3f}", "-i", fp])
            fc.append(f"[{kf}:v]format=rgba{fade},setpts=PTS+{t0:.4f}/TB[bf{j}]")
            fc.append(f"[{cur}][bf{j}]overlay={x - fpad}:{y - fpad}:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[cbf{j}]"); cur = f"cbf{j}"
            manifest["layers"].append({"path": str(fp), "kind": "broll_card", "x": x, "y": y, "w": tw, "h": th, "bbox": [0, 0, tw, th],
                                       "t0": t0, "t1": t1, "fade_in": b["fade_in"], "rise": 0})
            continue
        win = {"t0": t0, "t1": t1, "mode": b["mode"], "fade_in": b["fade_in"], "fade_out": b["fade_out"]}
        if b["mode"] == "full_pip":
            (px, py, pw, ph), (cx_, cy_, cw_, ch_) = b["pip"]["box"], b["pip"]["crop"]; src_ = pipsrcs[len(pipsrcs) - len(bpip) + bpip.index(b)]
            mp = B / f"broll{j}_pipmask.png"; g.pip_mask(mp, pw, ph, b["pip"].get("radius", 42))
            km = add_input(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", mp])
            fc.append(f"[{src_}]crop={cw_}:{ch_}:{cx_}:{cy_},scale={pw}:{ph},format=rgba[bpc{j}];[{km}:v]format=gray,scale={pw}:{ph}[bpm{j}];[bpc{j}][bpm{j}]alphamerge,"
                      f"fade=t=in:st={t0:.4f}:d=0.17:alpha=1,fade=t=out:st={t1 - 0.17:.4f}:d=0.17:alpha=1[bp{j}]")
            fc.append(f"[{cur}][bp{j}]overlay={px}:{py}:enable='between(t,{t0:.4f},{t1:.4f})'[cbp{j}]"); cur = f"cbp{j}"
            fp = B / f"broll{j}_pipframe.png"; fsz, fpad = g.video_frame(fp, pw, ph, b["pip"].get("radius", 42), st.c["teal"])
            kf = add_input(["-loop", "1", "-framerate", str(FPS), "-t", f"{d_ + 0.1:.3f}", "-i", fp])
            fc.append(f"[{kf}:v]format=rgba,fade=t=in:st=0:d=0.17:alpha=1,fade=t=out:st={d_ - 0.17:.3f}:d=0.17:alpha=1,setpts=PTS+{t0:.4f}/TB[bpf{j}]")
            fc.append(f"[{cur}][bpf{j}]overlay={px - fpad}:{py - fpad}:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[cbpf{j}]"); cur = f"cbpf{j}"
            win.update(pip_box=b["pip"]["box"], pip_crop=b["pip"]["crop"])
        manifest["camera_windows"].append(win)
    if slide:
        pm = B / "pip_mask.png"; g.pip_mask(pm, pip[2], pip[3], slide["pip"].get("radius", 42))
        im_pm = add_input(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", pm])
        cx_, cy_, cw_, ch_ = slide["pip"]["crop"]  # crop of the already-scaled output frame: x, y, w, h
        fc.append(f"[vpipsrc]crop={cw_}:{ch_}:{cx_}:{cy_},scale={pip[2]}:{pip[3]},format=rgba[pipc];[{im_pm}:v]format=gray,scale={pip[2]}:{pip[3]}[pipm];[pipc][pipm]alphamerge[pip]")
        for (png, t0, t1, fi, fo) in slide_layers:
            k = add_input(["-loop", "1", "-framerate", str(FPS), "-t", f"{t1 - t0 + 0.1:.3f}", "-i", png])
            fl = "format=rgba" + (f",fade=t=in:st=0:d={fi}:alpha=1" if fi else "") + (f",fade=t=out:st={t1-t0-fo:.3f}:d={fo}:alpha=1" if fo else "")
            fc.append(f"[{k}:v]{fl},setpts=PTS+{t0:.4f}/TB[ov{k}]")
            fc.append(f"[{cur}][ov{k}]overlay=0:0:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[c{k}]"); cur = f"c{k}"
        sa, sb = tl.slide; pf = slide.get("pip_fade", 0.17)
        fc.append(f"[pip]fade=t=in:st={sa:.4f}:d={pf}:alpha=1,fade=t=out:st={sb-pf:.4f}:d={pf}:alpha=1[pipf]")
        fc.append(f"[{cur}][pipf]overlay={pip[0]}:{pip[1]}:enable='between(t,{sa:.4f},{sb:.4f})'[cpip]"); cur = "cpip"
    for (png, x, y, t0, t1, fi, fo, rise) in overlays:
        d_ = t1 - t0
        with g.Image.open(png) as im_:
            ow, oh = im_.size; bb = im_.convert("RGBA").split()[3].point(lambda v: 255 if v > 24 else 0).getbbox()
        manifest["layers"].append({"path": str(png), "kind": "caption" if Path(png).name.startswith("cap") else Path(png).stem.split("_", 1)[-1],
                                   "x": x, "y": y, "w": ow, "h": oh, "bbox": list(bb) if bb else None,
                                   "t0": t0, "t1": t1, "fade_in": fi, "rise": rise})
        k = add_input(["-loop", "1", "-framerate", str(FPS), "-t", f"{d_ + 0.1:.3f}", "-i", png])
        f = "format=rgba"
        if fi: f += f",fade=t=in:st=0:d={fi}:alpha=1"
        if fo: f += f",fade=t=out:st={d_-fo:.3f}:d={fo}:alpha=1"
        fc.append(f"[{k}:v]{f},setpts=PTS+{t0:.4f}/TB[ov{k}]")
        yexpr = f"{y}+{rise}*max(0\\,1-(t-{t0:.4f})/0.3)" if rise else f"{y}"
        fc.append(f"[{cur}][ov{k}]overlay=x={x}:y='{yexpr}':eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[c{k}]"); cur = f"c{k}"
        manifest["overlays"].append({"png": os.path.basename(png), "x": x, "y": y, "t0": t0, "t1": t1})
    in_range = plan.get("source_range", "pc")  # DJI full-range (yuvj420p) -> broadcast tv range
    fc.append(f"[{cur}]scale=in_range={in_range}:out_range=tv,format=yuv420p[vout]")

    # audio: voice clean; music ducked under voice; sfx; loudness
    names = []; mix_in = "[voice]"
    k_m = add_input(["-i", mus_file]) if mus else None
    sfx_k = [add_input(["-i", f]) for f, *_ in sfx_list]
    fc.append(f"[acat]{VOICE_CHAIN},asplit[voice][sc]" if mus else f"[acat]{VOICE_CHAIN}[voice]")
    if mus:
        fc.append(f"[{k_m}:a]volume={mus.get('gain_db', -17)}dB[mus0];[mus0][sc]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=450[musd]")
        mix_in += "[musd]"
    for j, (k, (f, t, gdb, name)) in enumerate(zip(sfx_k, sfx_list)):
        ms = max(0, int(t * 1000))
        fc.append(f"[{k}:a]volume={gdb}dB,adelay={ms}|{ms}[sfx{j}]"); names.append(f"[sfx{j}]")
        manifest.setdefault("sfx", []).append({"file": name, "at_s": t, "gain_db": gdb})
    ln = aud.get("loudnorm", {"I": -14, "TP": -1.5, "LRA": 9})
    n_in = 1 + (1 if mus else 0) + len(names)
    fc.append(f"{mix_in}{''.join(names)}amix=inputs={n_in}:normalize=0:duration=first,loudnorm=I={ln['I']}:TP={ln['TP']}:LRA={ln['LRA']},aresample=48000,atrim=end={dur:.4f}[aout]")

    graph = ";\n".join(fc)
    if preview:
        graph = graph.replace(",format=yuv420p[vout]", f",scale={W//2}:{H//2}:flags=bicubic,format=yuv420p[vout]")
    gpath = work / "filter_graph.txt"; gpath.write_text(graph)
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26"] if preview else \
          ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high"]
    frames = min(tl.total, round(until * FPS)) if until is not None else tl.total  # --until: first S seconds only (hook previews)
    cmd = ["ffmpeg", "-v", "error", "-stats", "-n", *inputs, "-filter_complex_script", str(gpath),
           "-map", "[vout]", "-map", "[aout]", "-frames:v", str(frames), *(["-t", f"{frames / FPS:.4f}"] if until is not None else []), "-r", str(FPS), *enc,
           "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out_path)]
    (work / "render_cmd.json").write_text(json.dumps(cmd, indent=1, ensure_ascii=False))
    (B / "plan_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    if graph_only: return gpath
    subprocess.run(cmd, check=True)
    om = dict(manifest, output=str(out_path.resolve()), plan=str(plan_path), rendered_frames=frames, duration_s=frames / FPS,
              total_frames=frames, preview=preview)
    om["layers"] = [L for L in manifest["layers"] if L["t0"] < frames / FPS]
    Path(str(out_path)[:-4] + ".manifest.json").write_text(json.dumps(om, indent=1, ensure_ascii=False))
    qa = basic_qa(out_path, frames, FPS)
    Path(str(out_path)[:-4] + ".qa.json").write_text(json.dumps(qa, indent=1, ensure_ascii=False))
    print(json.dumps(qa, ensure_ascii=False))
    if not all(qa["checks"].values()): sys.exit(f"objective QA failed: {qa['checks']} (output kept for inspection, do not deliver)")
    return out_path


def basic_qa(path, frames, fps):
    """Objective checks only; status stays REVIEW until a human watches/listens."""
    pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)]))
    v = next(s for s in pr["streams"] if s["codec_type"] == "video"); a = next(s for s in pr["streams"] if s["codec_type"] == "audio")
    er = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a", "-af", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    summ = er[er.rfind("Summary:"):]
    pick = lambda key: float(summ.split(key)[1].split()[0]) if key in summ else None
    vd, ad = float(v.get("duration", 0)), float(a.get("duration", 0))
    return {"status": "REVIEW", "frames": int(v["nb_read_frames"]), "frames_expected": frames,
            "video_s": vd, "audio_s": ad, "av_diff_ms": round(abs(vd - ad) * 1000, 1),
            "color_range": v.get("color_range"), "lufs_i": pick("I:"), "true_peak_dbfs": pick("Peak:"),
            "checks": {"frames_ok": int(v["nb_read_frames"]) == frames, "av_ok": abs(vd - ad) < 0.05}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("out")
    ap.add_argument("--preview", action="store_true", help="540p veryfast preview")
    ap.add_argument("--graph-only", action="store_true", help="build assets + filter graph, do not render")
    ap.add_argument("--until", type=float, help="render only the first N seconds (quick hook/intro check)")
    a = ap.parse_args()
    if a.until is not None and not (0 < a.until < 1e5): sys.exit("--until must be a positive number of seconds")
    try: build(a.plan, a.out, a.preview, a.graph_only, a.until)
    except (ValueError, RuntimeError) as e: sys.exit(f"plan error: {e}")
