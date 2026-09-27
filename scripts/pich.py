#!/usr/bin/env python3
"""pich — raw talking-head video in, finished vertical Reel out, in one command.

    python3 pich.py RAW.mov [--out-dir DIR] [--lang tr] [--hook "EYEBROW|from|to"] [--cta "line 1|line 2|pill"]
                    [--music synth|none|FILE --music-rights-ok] [--plan-only]

Runs auto_plan.py -> render_reel.py (final) -> qa_reel.py and prints where the Reel and the QA report are.
With an AI agent (/pich), the agent reviews review.md, adds cards/icons/B-roll to plan.json and renders again.
Exit code: 0 = rendered and AUTO_PASS, 1 = QA found a problem (the file is kept for inspection), 2 = error.
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out-dir")
    ap.add_argument("--lang", default="auto"); ap.add_argument("--hook"); ap.add_argument("--cta")
    ap.add_argument("--music", default="synth"); ap.add_argument("--music-rights-ok", action="store_true")
    ap.add_argument("--plan-only", action="store_true", help="stop after plan.json + review.md")
    a = ap.parse_args()
    src = Path(a.src).expanduser().resolve()
    out = Path(a.out_dir or f"pich-{src.stem}").expanduser().resolve()
    cmd = [sys.executable, str(HERE / "auto_plan.py"), str(src), "--out-dir", str(out), "--lang", a.lang, "--music", a.music]
    for flag, v in (("--hook", a.hook), ("--cta", a.cta)):
        if v: cmd += [flag, v]
    if a.music_rights_ok: cmd.append("--music-rights-ok")
    if subprocess.run(cmd).returncode: sys.exit(2)
    if a.plan_only: return
    n = 1
    while (out / f"{src.stem}-pich-v{n}.mp4").exists(): n += 1
    reel = out / f"{src.stem}-pich-v{n}.mp4"
    r = subprocess.run([sys.executable, str(HERE / "render_reel.py"), str(out / "plan.json"), str(reel)], capture_output=True, text=True)
    if r.returncode and not reel.exists(): sys.stderr.write(r.stderr[-1500:]); sys.exit(2)
    q = subprocess.run([sys.executable, str(HERE / "qa_reel.py"), str(reel), "--plan", str(out / "plan.json")], capture_output=True, text=True)
    rep = json.loads(Path(str(reel)[:-4] + ".autoqa.json").read_text())
    print(f"\nReel:   {reel}\nQA:     {rep['status']}  fails={rep['fails']}  warns={rep['warns']}\nReport: {str(reel)[:-4]}.autoqa.jpg\nReview: {out / 'review.md'}")
    sys.exit(0 if rep["status"] == "AUTO_PASS" and not r.returncode else 1)


if __name__ == "__main__":
    main()
