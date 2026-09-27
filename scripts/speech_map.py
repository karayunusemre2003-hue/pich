#!/usr/bin/env python3
"""Speech map from the RMS envelope (stdlib only).

    python3 speech_map.py SOURCE.mp4 [--out speech_map.json] [--threshold-db -40] [--min-pause 0.35]
    python3 speech_map.py SOURCE.mp4 --check-plan plan.json [--edge-max-db -45]

1) Speech intervals + pauses (cut candidates) from a 10 ms RMS envelope.
2) --check-plan: for every EDL segment measure the 40 ms in/out edge level; an edge louder than
   --edge-max-db means the cut lands inside speech (clipped syllable) -> FAIL. Also reports the
   minimum level in the last 300 ms, which exposes a cut that trims the tail of the final word.
Cut suggestions are advisory; the editor decides from listening + transcript.
"""
import argparse, array, json, math, subprocess, sys, tempfile, wave
from pathlib import Path

SR = 16000


def load_pcm(src):
    tmp = Path(tempfile.mkdtemp()) / "a16.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(tmp)], check=True)
    w = wave.open(str(tmp)); d = array.array("h", w.readframes(w.getnframes())); w.close()
    if sys.byteorder == "big": d.byteswap()
    return d


def db(d, a, b):
    s = d[max(0, int(a * SR)):max(0, int(b * SR))]
    if not s: return -120.0
    r = math.sqrt(sum(x * x for x in s) / len(s))
    return round(20 * math.log10(r / 32768 + 1e-9), 1)


def envelope(d, step_s=0.01):
    step = int(SR * step_s)
    return [db(d, i / SR, (i + step) / SR) for i in range(0, len(d), step)]


def speech_intervals(env, step_s, thr, min_pause, min_speech=0.08):
    raw, cur = [], None
    for i, v in enumerate(env):
        t = i * step_s
        if v > thr and cur is None: cur = t
        elif v <= thr and cur is not None: raw.append([cur, t]); cur = None
    if cur is not None: raw.append([cur, len(env) * step_s])
    merged = []
    for a, b in raw:  # bridge pauses shorter than min_pause (breaths inside a phrase)
        if merged and a - merged[-1][1] < min_pause: merged[-1][1] = b
        else: merged.append([a, b])
    return [[round(a, 2), round(b, 2)] for a, b in merged if b - a >= min_speech]


def check_plan(d, plan_path, edge_max_db):
    plan = json.loads(Path(plan_path).read_text()); fps = plan.get("fps", 30)
    rows, ok, dur = [], True, len(d) / SR
    for i, s in enumerate(plan["edl"]):
        a, b = round(s["start"] * fps) / fps, round(s["end"] * fps) / fps
        if not (0 <= a < b <= dur + 1 / fps):
            rows.append({"seg": i, "start": a, "end": b, "label": s.get("label", ""), "pass": False,
                         "error": f"segment outside 0..{dur:.3f} s or empty"}); ok = False; continue
        r = {"seg": i, "start": a, "end": b, "label": s.get("label", ""),
             "in_edge_db": db(d, a, a + 0.04), "pre_db": db(d, a - 0.04, a),
             "out_edge_db": db(d, b - 0.04, b), "post_db": db(d, b, b + 0.04),
             "tail_min_db": min(db(d, b - 0.3 + k * 0.02, b - 0.28 + k * 0.02) for k in range(15))}
        r["pass"] = r["in_edge_db"] <= edge_max_db and r["out_edge_db"] <= edge_max_db
        ok &= r["pass"]; rows.append(r)
    return {"edge_max_db": edge_max_db, "status": "PASS" if ok else "FAIL", "segments": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("--out")
    ap.add_argument("--threshold-db", type=float, default=-40.0)
    ap.add_argument("--min-pause", type=float, default=0.35)
    ap.add_argument("--check-plan"); ap.add_argument("--edge-max-db", type=float, default=-45.0)
    a = ap.parse_args()
    d = load_pcm(a.source)
    if a.check_plan:
        res = check_plan(d, a.check_plan, a.edge_max_db)
        for r in res["segments"]:
            if "error" in r: print(f"BAD seg{r['seg']} {r['start']:.3f}-{r['end']:.3f} {r['error']}"); continue
            print(f"{'OK ' if r['pass'] else 'BAD'} seg{r['seg']} {r['start']:.3f}-{r['end']:.3f} in {r['in_edge_db']:.0f} dB | out {r['out_edge_db']:.0f} dB | tail-min {r['tail_min_db']:.0f} dB  {r['label'][:40]}")
        print(res["status"])
    else:
        step = 0.01; env = envelope(d, step)
        sp = speech_intervals(env, step, a.threshold_db, a.min_pause)
        pauses = [{"start": sp[i][1], "end": sp[i + 1][0], "dur": round(sp[i + 1][0] - sp[i][1], 2)} for i in range(len(sp) - 1)]
        res = {"source": str(a.source), "duration_s": round(len(d) / SR, 3), "threshold_db": a.threshold_db, "min_pause_s": a.min_pause,
               "speech": sp, "pauses": pauses,
               "cut_candidates": [p for p in pauses if p["dur"] >= 0.6],
               "note": "Advisory. Keep ~60-120 ms air around cuts; never cut on RMS alone - check the transcript."}
        print(f"{len(sp)} speech intervals, {len(res['cut_candidates'])} pauses >= 0.6 s")
    if a.out: Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))
    sys.exit(1 if res.get("status") == "FAIL" else 0)


if __name__ == "__main__":
    main()
