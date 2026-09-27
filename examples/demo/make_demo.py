#!/usr/bin/env python3
"""Build a self-contained demo: a synthetic 12 s vertical "talking head" (test pattern + speech-like tone
bursts), a 4 s B-roll clip, and plan.json using hook, captions, a step slide with PiP, an info card, a B-roll
card and a CTA. No network, no API keys, no personal footage.

    python3 examples/demo/make_demo.py
    python3 scripts/render_reel.py examples/demo/plan.json demo.mp4 --preview
    python3 scripts/qa_reel.py demo.mp4 --plan examples/demo/plan.json --no-asr
"""
import json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
# "phrases" of speech-like sound: (start, end)
PHRASES = [(0.6, 2.4), (2.9, 4.6), (5.1, 6.9), (7.4, 9.2), (9.7, 11.2)]


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def main():
    gate = "+".join(f"between(t\\,{a}\\,{b})" for a, b in PHRASES)
    ff("-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=12",
       "-f", "lavfi", "-i", f"aevalsrc=(0.35*sin(2*PI*180*t)+0.2*sin(2*PI*410*t))*(0.6+0.4*sin(2*PI*5*t))*({gate}):s=48000:d=12",
       "-c:v", "libx264", "-pix_fmt", "yuvj420p", "-c:a", "aac", "-shortest", str(HERE / "source.mp4"))
    ff("-f", "lavfi", "-i", "mandelbrot=size=640x360:rate=25", "-t", "4", "-c:v", "libx264", str(HERE / "broll.mp4"))
    air = 0.12
    edl = [{"start": round(a - air, 2), "end": round(b + air, 2), "label": f"P{i + 1}"} for i, (a, b) in enumerate(PHRASES)]
    edl[-1]["volume"] = 1.0
    words = [["This is a demo", "of the renderer."], ["Hooks, captions", "and cards"], ["are timed to", "the speech."],
             ["Steps light up", "while you talk."], ["Swap in your", "own footage."]]
    caps = []
    for i, ((a, b), pair) in enumerate(zip(PHRASES, words)):
        mid = (a + b) / 2
        caps += [{"seg": i, "start": a, "end": mid, "text": pair[0]}, {"seg": i, "start": mid, "end": b, "text": pair[1], "hl": pair[1].split()[-1:]}]
    plan = {
        "source": "source.mp4", "build_dir": "build", "fps": 30, "width": 1080, "height": 1920,
        "source_size": [1080, 1920], "crop_anchor_y": 0.28, "source_range": "pc",
        "edl": edl,
        "slide": {"start": {"seg": 3, "t": "start"}, "end": {"seg": 3, "t": "end"}, "eyebrow": "HOW IT WORKS",
                  "title": ["Plan in,", "Reel out"],
                  "steps": [{"icon": "chat", "label": "Transcribe the take", "at": {"seg": 3, "t": "start"}},
                            {"icon": "code", "label": "Write plan.json", "at": {"seg": 3, "t": 8.0}},
                            {"icon": "gear", "label": "Render + QA", "at": {"seg": 3, "t": 8.6}}],
                  "pip": {"box": [584, 540, 440, 600], "crop": [270, 500, 540, 736]}},
        "layers": [
            {"kind": "hook_card", "eyebrow": "DEMO", "from_text": "Raw take", "to_text": "finished Reel", "y": 250,
             "from": "start", "to": {"seg": 0, "t": "end", "offset": -0.05}, "fade_out": 0.2},
            {"kind": "hook_card", "eyebrow": "TIMED TO SPEECH", "from_text": "Words", "to_text": "cards", "y": 300,
             "from": {"seg": 1, "t": "start"}, "to": {"seg": 1, "t": "end"}, "fade_in": 0.15, "fade_out": 0.15, "rise": 12},
            {"kind": "broll", "mode": "card", "src": "broll.mp4", "width": 600, "y": 280,
             "from": {"seg": 2, "t": "start"}, "to": {"seg": 2, "t": "end"}},
            {"kind": "cta_card", "lines": ["Try it on", "your own video"], "pill": "Star the repo", "y": 300,
             "from": {"seg": 4, "t": "start"}, "to": "end", "fade_in": 0.25, "rise": 20},
        ],
        "captions": {"y": 0.72, "items": caps},
        "audio": {"music": {"synth": "pad", "gain_db": -18},
                  "sfx": [{"synth": "whoosh", "at": {"slide": "start", "offset": -0.3}, "gain_db": -21},
                          {"synth": "chime", "at": {"seg": 4, "t": "start", "offset": 0.1}, "gain_db": -20}],
                  "loudnorm": {"I": -14, "TP": -1.5, "LRA": 9}},
    }
    (HERE / "plan.json").write_text(json.dumps(plan, indent=1))
    print(f"wrote {HERE / 'source.mp4'}, {HERE / 'broll.mp4'}, {HERE / 'plan.json'}")


if __name__ == "__main__":
    main()
