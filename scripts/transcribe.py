#!/usr/bin/env python3
"""Word-level Turkish transcript with a suspicious-word report (whisper.cpp `whisper-cli`).

    python3 transcribe.py SOURCE.mp4 --out transcript.json [--model M.bin] [--second-model M2.bin] [--lang tr] [--start S --end E]

Why: a single Whisper pass drifts word times (~0.4 s), invents words in silence and mishears proper
names. So this script never returns a bare transcript. It flags:
  - low_conf : mean token probability < --min-p
  - isolated : the same speech phrase transcribed alone (clip cut at speech_map.py edges, no
               surrounding context) gives a different word (catches misheard names)
  - off_speech: no speech phrase near the word and the whole window is quieter than --silent-db
               (hallucination like "Evet" in silence, OR a drifted time — use the phrase times)
  - model2   : optional --second-model disagrees
Output also lists speech phrases with their isolated text and edge-accurate times (caption source).
Flagged proper names/verbs are cut or confirmed with the speaker — never guessed. Captions come from the
reviewed text, timing from speech_map.py + these word times.
Models: $PICH_MODELS_DIR (default ~/.local/share/whisper-models) — run scripts/setup_models.sh once.
"""
import argparse, difflib, json, os, re, subprocess, sys, tempfile, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from speech_map import SR, db, envelope, load_pcm, speech_intervals  # noqa: E402

MODELS_DIR = Path(os.environ.get("PICH_MODELS_DIR", Path.home() / ".local/share/whisper-models")).expanduser()
DEFAULT_MODEL = Path(os.environ.get("PICH_WHISPER_MODEL", MODELS_DIR / "ggml-large-v3-turbo-q5_0.bin")).expanduser()
SECOND_MODEL = Path(os.environ.get("PICH_WHISPER_MODEL2", MODELS_DIR / "ggml-medium.bin")).expanduser()


def whisper_words(wav, model, lang, start=None, end=None):
    out = Path(tempfile.mkdtemp()) / "w"
    cmd = ["whisper-cli", "-m", str(model), "-l", lang, "-f", str(wav), "-ml", "1", "-sow", "-ojf", "-of", str(out), "-np"]
    if start is not None: cmd += ["-ot", str(int(start * 1000))]
    if end is not None: cmd += ["-d", str(int((end - (start or 0)) * 1000))]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    words = []
    for s in json.loads(Path(str(out) + ".json").read_text())["transcription"]:
        w = s["text"].strip()
        if not w: continue
        ps = [t["p"] for t in s["tokens"] if not t["text"].startswith("[_")]
        words.append({"w": w, "start": s["offsets"]["from"] / 1000, "end": s["offsets"]["to"] / 1000,
                      "p": round(sum(ps) / len(ps), 3) if ps else 0.0})
    return words


def norm(w):
    return re.sub(r"[^\wçğıöşüâîû]", "", w.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=str(DEFAULT_MODEL), help="primary ggml model")
    ap.add_argument("--second-model", default=str(SECOND_MODEL) if SECOND_MODEL.exists() else None,
                    help="second ggml model for a cross-check (default: ggml-medium.bin when installed)")
    ap.add_argument("--single", action="store_true", help="skip the second-model cross-check (faster)")
    ap.add_argument("--lang", default="tr")
    ap.add_argument("--start", type=float); ap.add_argument("--end", type=float)
    ap.add_argument("--min-p", type=float, default=0.5)
    ap.add_argument("--silent-db", type=float, default=-45.0)
    a = ap.parse_args()
    models = [Path(m).expanduser() for m in [a.model] + ([a.second_model] if a.second_model and not a.single else [])]
    for m in models:
        if not m.exists(): sys.exit(f"model not found: {m}")

    tmp = Path(tempfile.mkdtemp()) / "a16.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.source, "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(tmp)], check=True)
    pcm = load_pcm(tmp)

    words = whisper_words(tmp, models[0], a.lang, a.start, a.end)
    lo, hi = a.start or 0.0, a.end or len(pcm) / SR
    phrases = [p for p in speech_intervals(envelope(pcm), 0.01, -40.0, 0.35) if p[1] > lo and p[0] < hi]

    # isolated pass: every speech phrase alone, times shifted back to source seconds
    iso_words, iso_phr = [], []
    for p0, p1 in phrases:
        c0, c1 = max(0.0, p0 - 0.15), p1 + 0.15
        clip = Path(tempfile.mkdtemp()) / "p.wav"
        with wave.open(str(clip), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(pcm[int(c0 * SR):int(c1 * SR)].tobytes())
        ws = whisper_words(clip, models[0], a.lang)
        for x in ws: x["start"] = round(x["start"] + c0, 2); x["end"] = round(x["end"] + c0, 2)
        iso_words += ws
        iso_phr.append({"start": p0, "end": p1, "text": " ".join(x["w"] for x in ws)})

    def near_speech(t):
        return any(p0 - 0.3 <= t <= p1 + 0.3 for p0, p1 in phrases)

    for w in words:
        w["flags"] = []
        if w["p"] < a.min_p: w["flags"].append("low_conf")
        mid = (w["start"] + w["end"]) / 2
        peak = max(db(pcm, t / 100, t / 100 + 0.02) for t in range(int((w["start"] - 0.2) * 100), int((w["end"] + 0.2) * 100) + 1))
        if not near_speech(mid) and peak < a.silent_db: w["flags"].append("off_speech")

    def cross(other, flag):
        sm = difflib.SequenceMatcher(a=[norm(w["w"]) for w in words], b=[norm(w["w"]) for w in other], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal": continue
            alt = " ".join(w["w"] for w in other[j1:j2]) or "(yok)"
            hit = words[i1:i2] or words[max(0, i1 - 1):i1 + 1]  # insert: the primary pass dropped words here
            for w in hit:
                if flag not in w["flags"]: w["flags"].append(flag)
                w[flag + "_alt"] = f"(buraya eksik) {alt}" if tag == "insert" else alt

    cross(iso_words, "isolated")
    if len(models) > 1:
        words2 = whisper_words(tmp, models[1], a.lang, a.start, a.end); cross(words2, "model2")

    suspects = [{"i": i, "word": w["w"], "start": w["start"], "end": w["end"], "flags": w["flags"],
                 **{k: w[k] for k in ("isolated_alt", "model2_alt") if k in w}}
                for i, w in enumerate(words) if w["flags"]]

    res = {"source": a.source, "models": [m.name for m in models], "lang": a.lang,
           "text": " ".join(w["w"] for w in words), "phrases": iso_phr, "words": words, "words_model2": words2 if len(models) > 1 else [], "suspects": suspects,
           "status": "REVIEW" if suspects else "CLEAN",
           "note": "Word times drift ~0.1-0.4 s; snap cuts to speech_map.py edges. Resolve every suspect before captions."}
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"{len(words)} words, {len(suspects)} suspects -> {a.out}")
    for s in suspects:
        alts = " | ".join(f"{k[:-4]}: {s[k]!r}" for k in ("isolated_alt", "model2_alt") if k in s)
        print(f"  ? {s['start']:7.2f}s {s['word']!r} {s['flags']} {alts}")


if __name__ == "__main__":
    main()
