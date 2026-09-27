#!/usr/bin/env python3
"""Raw talking-head clip -> a ready plan.json (the automatic first pass of /pich).

    python3 auto_plan.py RAW.mov --out-dir PROJECT [--lang tr] [--hook "EYEBROW|from|to"] [--cta "line 1|line 2|pill"]
                         [--music synth|none|FILE --music-rights-ok]

What it decides on its own:
  * conforms the source to CFR 30 fps and a 9:16 frame (center crop) when needed
  * one EDL segment per speech phrase, with air, each end extended until the breath tail is quiet (<= -48 dB)
  * captions from the verified transcript (turbo + medium + isolated pass), never splitting a number from its unit,
    numbers highlighted
  * caption height from where the face actually is (macOS Vision): low face -> captions above the head
  * music ducked under the voice, loudness -14 LUFS; optional hook card on frame 0 and CTA on a quiet tail
Writes PROJECT/plan.json and PROJECT/review.md (words the models disagreed on — check them before publishing).
An agent (or you) can then add cards, icons, B-roll or a motion segment to plan.json and render.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from speech_map import SR, db, envelope, load_pcm, speech_intervals  # noqa: E402

AIR, FLOOR = 0.12, -48.0


def probe(path):
    st = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height,r_frame_rate,avg_frame_rate:stream_side_data=rotation:format=duration",
                                             "-of", "json", str(path)]))
    s = st["streams"][0]; frac = lambda v: (lambda n, d: n / d if d else 0)(*map(int, v.split("/")))
    w, h = s["width"], s["height"]
    rot = next((abs(int(float(sd.get("rotation", 0)))) for sd in s.get("side_data_list", []) if "rotation" in sd), 0)
    if rot % 180 == 90: w, h = h, w
    return w, h, frac(s["r_frame_rate"]), frac(s["avg_frame_rate"]), float(st["format"]["duration"])


def conform(src, out_dir):
    """CFR 30 fps and 9:16; returns (path, width, height)."""
    w, h, r, avg, _ = probe(src)
    vertical = abs(w / h - 9 / 16) < 0.01
    if abs(r - 30) < 0.01 and abs(avg - 30) < 0.05 and vertical:
        return Path(src), w, h
    vf = [] if vertical else ["crop=trunc(ih*9/16/2)*2:ih" if w / h > 9 / 16 else "crop=iw:trunc(iw*16/9/2)*2"]
    dst = out_dir / "source_conformed.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *(["-vf", ",".join(vf)] if vf else []), "-fps_mode", "cfr", "-r", "30",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-c:a", "aac", "-b:a", "256k", str(dst)], check=True)
    w, h, *_ = probe(dst)
    return dst, w, h


def chunks(text, maxc=24):
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if len(t) <= maxc or not cur: cur = t
        else:
            last = cur.split()[-1]
            if re.fullmatch(r"[\d.,%]+", last) and " " in cur:  # never strand a number away from its unit
                out.append(cur.rsplit(" ", 1)[0]); cur = last + " " + w
            else: out.append(cur); cur = w
        if cur.endswith((",", ".", "?", "!", ":")) and len(cur) >= 8: out.append(cur); cur = ""
    if cur: out.append(cur)
    return out


def vote(phrase, t):
    """Caption text for one phrase. Base = the isolated pass (clean phrase boundaries). A word is replaced only when
    the full turbo pass AND the medium pass both read that spot the same, different way (a single pass alone can
    turn "3 saat sürdü" into "3 sualçı"). Words the two others don't agree on stay as they are and go to review.md."""
    import difflib
    base = phrase["text"].split()
    lo, hi = phrase["start"] - 0.5, phrase["end"] + 0.5
    near = lambda ws: [w["w"] for w in ws if lo <= (w["start"] + w["end"]) / 2 <= hi]
    full, m2 = near(t.get("words", [])), near(t.get("words_model2", []))
    if not full or not m2: return " ".join(base)
    norm = lambda w: re.sub(r"[^\wçğıöşüâîû]", "", w.lower().translate(str.maketrans("âîû", "aiu")))

    def alt(other):  # base token span (i1, i2) -> the other pass's reading of it
        sm = difflib.SequenceMatcher(a=[norm(w) for w in base], b=[norm(w) for w in other], autojunk=False)
        return {(i1, i2): other[j1:j2] for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag == "replace"}
    af, am = alt(full), alt(m2)
    out, k = [], 0
    for (i1, i2), words in sorted(af.items()):
        mw = am.get((i1, i2))
        if mw is not None and [norm(w) for w in mw] == [norm(w) for w in words]:
            out += base[k:i1] + words; k = i2
    return " ".join(out + base[k:])


def caption_height(src, dur, w, h):
    """Look at 5 frames with macOS Vision; returns (caption y, note)."""
    if sys.platform != "darwin": return 0.72, "no face check on this OS: captions at the usual lower lane — check the face by eye"
    import tempfile
    import qa_reel
    tmp = Path(tempfile.mkdtemp()); frames = []
    for i in range(5):
        f = tmp / f"f{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * (i + 0.5) / 5:.2f}", "-i", str(src), "-frames:v", "1",
                        "-vf", f"scale={w // 2}:{h // 2}", str(f)], check=True)
        frames.append(f)
    res = json.loads(subprocess.check_output([str(qa_reel.face_binary())] + [str(f) for f in frames]))
    faces = [b for f in frames for b in res.get(str(f), [])[:1]]
    if not faces: return 0.72, "no face found: captions at the usual lower lane"
    bottom = sorted(b[1] + b[3] for b in faces)[len(faces) // 2]; top = sorted(b[1] - 0.25 * b[3] for b in faces)[len(faces) // 2]
    if bottom < 0.64: return 0.74, f"face above the lower lane (chin ~{bottom:.2f}): captions low"
    if top > 0.36: return 0.30, f"face sits low (chin ~{bottom:.2f}): captions above the head"
    return 0.74, f"face fills the frame (chin ~{bottom:.2f}): captions low — check the chin overlap in QA"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--lang", default="auto", help="whisper language code (tr, en, …) or auto")
    ap.add_argument("--hook", help='"EYEBROW|from text|to text" — shown on frame 0')
    ap.add_argument("--cta", help='"line 1|line 2|pill" — shown on a quiet tail after the last sentence')
    ap.add_argument("--music", default="synth", help="synth (generated, rights-free), none, or a file you hold the rights to")
    ap.add_argument("--music-rights-ok", action="store_true", help="confirm you hold the rights to --music FILE")
    a = ap.parse_args()
    out = Path(a.out_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
    src, W0, H0 = conform(Path(a.src).expanduser().resolve(), out)
    *_, dur = probe(src)

    pcm = load_pcm(src)
    phrases = speech_intervals(envelope(pcm), 0.01, -40.0, 0.35)
    if not phrases: sys.exit("no speech found")
    tr = out / "transcript.json"
    subprocess.run([sys.executable, str(HERE / "transcribe.py"), str(src), "--out", str(tr), "--lang", a.lang], check=True, stdout=subprocess.DEVNULL)
    t = json.loads(tr.read_text())
    texts = {(p["start"], p["end"]): vote(p, t) for p in t["phrases"]}

    def quiet_after(x, limit):
        while x < limit and db(pcm, x - 0.04, x) > FLOOR: x += 0.01
        return min(x, limit)

    def quiet_before(x, limit):
        while x > limit and db(pcm, x, x + 0.04) > FLOOR: x -= 0.01
        return max(x, limit)

    kept = [(a_, b_, texts.get((a_, b_), "")) for a_, b_ in phrases]
    kept = [k for k in kept if k[2]]
    edl, caps = [], []
    for i, (s0, s1, text) in enumerate(kept):
        lo_lim = (kept[i - 1][1] + s0) / 2 if i else 0.0
        hi_lim = (s1 + kept[i + 1][0]) / 2 if i + 1 < len(kept) else min(dur, s1 + 0.8)
        lo = quiet_before(max(s0 - AIR, lo_lim), lo_lim); hi = quiet_after(min(s1 + AIR, hi_lim), hi_lim)
        edl.append({"start": round(lo, 2), "end": round(hi, 2), "label": text[:48]})
        parts = chunks(text); total = sum(len(p) for p in parts) or 1; x = s0
        for p in parts:
            d = (s1 - s0) * len(p) / total
            caps.append({"seg": i, "start": round(x, 2), "end": round(x + d, 2), "text": p,
                         "hl": [w for w in p.split() if re.search(r"\d", w)]})
            x += d
    last = len(edl) - 1
    if a.cta:
        tail0 = edl[-1]["end"]; tail1 = min(dur - 0.05, tail0 + 2.2)
        if tail1 - tail0 < 1.2: sys.exit("--cta needs ~1.5 s of quiet after the last sentence; re-shoot with a short pause at the end")
        edl.append({"start": round(tail0, 2), "end": round(tail1, 2), "label": "TAIL CTA", "volume": 0.35})
    cap_y, cap_note = caption_height(src, dur, W0, H0)

    layers = []
    if a.hook:
        eb, f_, t_ = (a.hook.split("|") + ["", "", ""])[:3]
        layers.append({"kind": "hook_card", "eyebrow": eb.upper(), "from_text": f_, "to_text": t_, "y": 250 if cap_y > 0.5 else 130,
                       "from": "start", "to": {"seg": 0, "t": "end", "offset": -0.05}, "fade_out": 0.2})
    if a.cta:
        l1, l2, pill = (a.cta.split("|") + ["", "", ""])[:3]
        layers.append({"kind": "cta_card", "lines": [l1, l2], "pill": pill or "Follow", "y": 300,
                       "from": {"seg": last + 1, "t": "start", "offset": 0.1}, "to": "end", "fade_in": 0.25, "rise": 20})
    audio = {"loudnorm": {"I": -14, "TP": -1.5, "LRA": 9}}
    if a.music == "synth": audio["music"] = {"synth": "pad", "gain_db": -18}
    elif a.music != "none":
        if not a.music_rights_ok: sys.exit("--music FILE needs --music-rights-ok (you must hold the rights)")
        audio["music"] = {"file": str(Path(a.music).expanduser().resolve()), "gain_db": -24, "rights_checked": True}
    if a.cta: audio["sfx"] = [{"synth": "chime", "at": {"seg": last + 1, "t": "start", "offset": 0.08}, "gain_db": -20}]
    plan = {"_note": "auto_plan.py first pass — add cards, icons, B-roll or a motion segment, then render.",
            "source": str(src), "build_dir": "build", "fps": 30, "width": 1080, "height": 1920, "source_size": [W0, H0],
            "crop_anchor_y": 0.28, "source_range": "pc", "edl": edl, "layers": layers,
            "captions": {"y": cap_y, "bridge_gap_s": 0.25, "items": caps}, "audio": audio}
    (out / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    sus = t.get("suspects", [])
    lines = [f"# Review before publishing\n\nSource: {src}\nCaptions: y={cap_y} — {cap_note}\n",
             f"Kept {len(edl)} segments, {sum(e['end'] - e['start'] for e in edl):.1f} s of {dur:.1f} s.\n",
             "## Words the models disagreed on" if sus else "## Transcript: no suspicious words"]
    for s in sus:
        alts = ", ".join(f"{k[:-4]}: {s[k]!r}" for k in ("isolated_alt", "model2_alt") if k in s)
        lines.append(f"- {s['start']:.2f}s **{s['word']}** {s['flags']} {alts}")
    lines.append("\nFix a wrong word in plan.json → captions → items (text). Cut or confirm uncertain names — never guess.")
    (out / "review.md").write_text("\n".join(lines) + "\n")
    print(f"plan: {out / 'plan.json'}  ({len(edl)} segments, {len(caps)} captions, {len(sus)} words to review)")


if __name__ == "__main__":
    main()
