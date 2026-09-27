# Jarvis Video Studio

**Turn a raw talking-head clip into a finished vertical Reel — with an AI agent doing the editing and automatic QA
catching what humans miss.** A [Claude Code](https://docs.claude.com/en/docs/claude-code) skill (works with any
agent that can run shell commands) plus plain Python/FFmpeg scripts.

[Türkçe README](README.tr.md)

## What you get

From one `plan.json` and one FFmpeg pass:

- **Speech-safe cuts** — pauses removed, never a clipped syllable (every cut edge is measured).
- **Verified captions** — two Whisper models plus a per-phrase isolated pass flag misheard words before they become captions.
- **Hook card on frame 0**, info cards, **icons** (200k+ open-source via Iconify), verified **brand logos**.
- **Step slide with live PiP**, or a **brag-style [Hyperframes](https://github.com/heygen-com/hyperframes) motion
  segment** (animated counters, charts) with the speaker still on screen.
- **Stock B-roll** from Pexels: full-screen cutaways, or video cards over the camera.
- **Music ducked under the voice**, SFX, broadcast loudness (-14 LUFS).
- **Hook A/B previews**: render the first 3 s of several hooks side by side, pick one.

Then `qa_reel.py` checks the result: a layer covering the eyes or mouth (macOS Vision on the clean source frame),
captions the speaker doesn't actually say, music masking a word, A/V drift per segment, loudness, black last frame,
estimated Instagram UI overlap. Broken renders fail loudly, so you never post one by accident.

## Requirements

- macOS or Linux, Python 3.11+, `ffmpeg`/`ffprobe`, `pip install pillow`
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (`whisper-cli` on PATH) + models: `scripts/setup_models.sh` (~2 GB)
- Optional: Node 20+ for Hyperframes motion segments (`npx hyperframes`), `librsvg` (`rsvg-convert`) on Linux for icons/logos
- Optional keys (free): `PEXELS_API_KEY` for stock, `BRANDFETCH_API_KEY` for logos Simple Icons lacks
- The face check uses macOS Vision; on Linux it is skipped with a warning

## Install as a Claude Code skill

```bash
git clone https://github.com/<you>/jarvis-video-studio ~/.claude/skills/jarvis-video-studio
~/.claude/skills/jarvis-video-studio/scripts/setup_models.sh
```

Then give Claude a clip: *"Make a Reel from ~/Movies/take3.mov"*. The skill's `SKILL.md` walks the agent through
speech map → transcript review → cuts → layers → preview → final → QA.

## Try it without your own footage

```bash
python3 examples/demo/make_demo.py                     # synthetic 12 s source + B-roll + plan.json
python3 scripts/render_reel.py examples/demo/plan.json demo.mp4 --preview
python3 scripts/qa_reel.py demo.mp4 --plan examples/demo/plan.json --no-asr
```

`examples/motion-template/` is a ready Hyperframes segment ("When does it pay off?": setup hours → minutes saved
per day → break-even day → profit) to adapt for your own numbers.

## How it works

| Step | Tool |
|---|---|
| Speech phrases, pauses, cut-edge check | `scripts/speech_map.py` |
| Transcript with suspicious-word report | `scripts/transcribe.py` |
| Render plan.json (single FFmpeg pass) | `scripts/render_reel.py` — schema: [references/render-reel-plan.md](references/render-reel-plan.md) |
| Automatic QA | `scripts/qa_reel.py` |
| Hook A/B | `scripts/hook_variants.py` |
| Icons / stock / logos | `scripts/iconify.py`, `scripts/stock.py`, `scripts/fetch_logos.py` |

Every overlay is anchored to *source seconds inside a kept segment*, so changing the cuts never slides a card
away from the words it belongs to.

## Rights and privacy

- No music and no brand logos are bundled. Music needs `"rights_checked": true` (or the generated pad); logos need
  a source URL and a verification date. Trademarks belong to their owners — show a logo only when the brand is named.
- Stock and icons record author and license in the render manifest.
- Keys are read from environment variables only; nothing is uploaded except the API calls you run.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Synthetic fixtures (no footage needed), a golden filter graph for the demo plan, and QA that must FAIL on broken
renders. Tests that need network, keys or models skip themselves.

## License

MIT — see [LICENSE](LICENSE). Third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
