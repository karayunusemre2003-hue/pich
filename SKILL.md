---
name: jarvis-video-studio
description: Edit a talking-head video into a finished vertical Reel/Short/TikTok — verified transcript, speech-safe cuts, captions, hook, cards and icons, step slide or Hyperframes motion segment with live PiP, stock B-roll, ducked music, loudness — from one plan.json, then check it automatically (face overlap, captions vs speech, music masking, A/V sync, loudness). Use when someone gives you camera footage and wants a Reel, or asks to add captions, B-roll, a hook or a motion segment to a talking-head clip.
version: 0.6.1
license: MIT
---

# Jarvis Video Studio

Turns camera footage into a 1080×1920 Reel. You (the agent) make the editorial decisions; the scripts do the
deterministic work and refuse unsafe input. Nothing is published or sent anywhere.

`<skill-dir>` below is the folder containing this file.

## Procedure

1. **Probe + speech map.** `ffprobe` the source (full-range phone/DJI footage → `source_range: "pc"`). It must be
   constant frame rate at the plan fps; conform VFR clips first (`ffmpeg -i in.mov -fps_mode cfr -r 30 out.mp4`).
   `python3 <skill-dir>/scripts/speech_map.py SRC --out speech_map.json` → speech phrases and pauses.
2. **Transcript.** `python3 <skill-dir>/scripts/transcribe.py SRC --out transcript.json`. Two whisper.cpp models
   (turbo + medium, `scripts/setup_models.sh`) plus an isolated per-phrase pass; resolve every entry in `suspects`
   by listening. Uncertain names or verbs are cut or confirmed with the speaker — never guessed.
3. **EDL.** One segment per kept phrase, ~0.12 s of air, cuts only where it is quiet. Verify with
   `python3 <skill-dir>/scripts/speech_map.py SRC --check-plan plan.json` → must print PASS (no edge above -45 dB).
   Extend an end until the breath tail has decayed rather than clipping it.
4. **Plan the layers** ([plan schema](references/render-reel-plan.md), [which visual for which idea](references/visual-sources.md)).
   All times are anchored to *source seconds inside a segment*, so re-cutting never slides a layer off its words.
   - Hook card visible on frame 0, below the top ~220 px of Instagram chrome.
   - Captions from the reviewed text; never split a number from its unit. If the face sits low in the frame, put
     captions above the head (`y` ≈ 0.30); per-caption `y` moves them off a slide.
   - Cards/icons only for a specific spoken idea; never over the eyes or mouth.
   - Concrete scene → 1.5–3 s stock cutaway (`broll` `full`, `scripts/stock.py`).
   - Numbers, steps or a product demo → step slide, or a brag-style Hyperframes motion segment as `broll` `full_pip`
     so the face stays on screen ([recipe](references/motion-segments.md), [template](examples/motion-template/)).
   - CTA card on a quiet tail segment.
5. **Hook A/B (optional).** `python3 <skill-dir>/scripts/hook_variants.py plan.json variants.json --out-dir DIR`
   → 3 s previews in parallel + a side-by-side `hooks.jpg`; `--pick NAME` writes the final plan.
6. **Preview, then final.** `python3 <skill-dir>/scripts/render_reel.py plan.json preview.mp4 --preview [--until S]`
   (540p; 4K sources use a cached half-res proxy). Look at every layer boundary, then render the final under a new
   name. The renderer refuses to overwrite and exits non-zero if frame count or A/V length is off.
7. **Auto QA.** `python3 <skill-dir>/scripts/qa_reel.py final.mp4 --plan plan.json` → `final.autoqa.json` + `.jpg`.
   FAIL: a layer over the eyes/mouth (macOS Vision on the clean source frame; slide/B-roll/PiP aware), a caption the
   speaker doesn't say (voice stem rebuilt from the EDL), voice offset > 40 ms, loudness off -14 ±1.5 LUFS or true
   peak > -1 dBTP, black last frame. WARN: music masking a caption, layer on the chin, estimated Instagram UI overlap,
   no hook on frame 0. Fix every FAIL and re-render.
8. **Human QA.** Watch on a phone with headphones. `AUTO_PASS` is not approval.

## Audio

Music is `{"synth": "pad"}` (generated, rights-free) or your own licensed file with `"rights_checked": true`.
Voice chain → music ducked by sidechain (≈ -24 dB for tracks with drums) → SFX → `loudnorm I=-14 TP=-1.5`.
`scripts/finish_audio.py` re-scores an already rendered video.

## Scripts

| Script | Role |
|---|---|
| `render_reel.py` | plan.json → single-pass FFmpeg render; design presets, logos, icons, B-roll, proxy previews |
| `reel_graphics.py` | PIL templates: captions, hook/info card, step slide, image card, badge, wordmark, CTA |
| `qa_reel.py` + `face_detect.swift` | automatic QA report (face check needs macOS; skipped with a warning elsewhere) |
| `transcribe.py`, `speech_map.py` | verified transcript; speech phrases, pauses, cut-edge check |
| `hook_variants.py` | hook A/B previews and pick |
| `iconify.py` | 200k+ open-source icons (no key) as `icon` layers; license recorded per render |
| `stock.py` | Pexels photos/videos with a provenance sidecar (`PEXELS_API_KEY`) |
| `fetch_logos.py` + `svg2png.swift` | build your own verified logo library (Simple Icons; Brandfetch for owner-claimed brands) |
| `finish_audio.py` | optional audio re-mix of a finished video |
| `setup_models.sh` | download + SHA-1-verify the whisper.cpp models |

## Limits

Templates are laid out for 1080×1920. Instagram UI zones are an estimate — check on a phone. Face boxes are sampled
(every 0.5 s plus layer edges), not tracked. The repo ships no music and no brand logos.

## Verification

`python3 -m unittest discover -s <skill-dir>/tests -v` — synthetic FFmpeg fixtures, a golden filter graph for the
demo plan, QA that must FAIL on broken renders. Live-service tests skip without network/keys/models.
