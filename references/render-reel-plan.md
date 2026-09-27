# render_reel.py plan schema

Full working example: `examples/demo/plan.json` (built by `examples/demo/make_demo.py`). Relative paths resolve from the plan file; `~` is expanded.

## Top level
| Key | Default | Meaning |
|---|---|---|
| `source` | — | camera file with audio (read-only) |
| `build_dir` | `build` | generated PNG/WAV, manifest, filter graph — keep it next to the project, not inside your notes/repo |
| `fps`, `width`, `height` | 30, 1080, 1920 | output; templates are laid out for 1080×1920 |
| `source_size` | [2160, 3840] | source pixels (crop math) |
| `crop_anchor_y` | 0.28 | vertical anchor for zoom crops (keeps the face high) |
| `source_range` | `pc` | `pc` for DJI/iPhone full range, `tv` otherwise |
| `design` | `default` | preset in `assets/design/` (tokens, font, zones, estimated IG UI zones used by `qa_reel.py`) |
| `tokens`, `font` | from preset | override single colors `ink navy accent paper yellow teal chip_icon eyebrow` (RGB lists) / font file |

Plans are validated before any work: 1080×1920 only (template layout), numbers bounded, `rights_checked` must be literally `true`, source must be CFR at `fps`.

## Time references
Used by layer `from`/`to`, slide step `at`, slide `start`/`end` (not `{"slide": …}` there) and sfx `at`. EDL and caption `start`/`end` are plain **source seconds** (captions also need `seg`).
- `"start"` / `"end"` of the output, or a number (output seconds)
- `{"seg": i, "t": 69.38 | "start" | "end", "offset": -0.05}` — source seconds inside EDL segment i (clamped to it)
- `{"slide": "start" | "end", "offset": -0.3}` — slide window

## `edl`
`[{"start", "end", "zoom": 1.0, "label", "volume"}]` in playback order, source seconds (snapped to frames). `volume` e.g. 0.35 for a silent CTA tail.

## `slide` (optional, full-frame stepper + live PiP)
`start`, `end`, `eyebrow`, `title: [white line, yellow line]`, `steps: [{"icon", "label", "at"}]` (label: first word bold, rest below), `pip: {"box": [x,y,w,h], "crop": [x,y,w,h of the output frame], "radius"}`. Icons: image, code, gear, nodes, chat, arrow_down, arrow_right. Keep ≤ 8 s.

## `layers` (drawn in order, above slide)
Common: `y` (top of the card body; shadow padding is subtracted automatically), `x` (`"center"` or px), `from`, `to`, `fade_in`, `fade_out`, `rise` (px slide-up over 0.3 s).
- `hook_card`: `eyebrow`, `from_text`, `to_text` — put `from: "start"` so frame 0 shows it
- `image_card`: `src`, `width`, `provenance` (`image_gen` | `logo` | `stock`)
- `round_badge`: `src`, `size`
- `wordmark`: `text`
- `cta_card`: `lines` (2), `pill`
- `icon`: `icon: "prefix:name"` from Iconify (find names: `python3 scripts/iconify.py search bell`), `size` px (16–800, default 120), `color` = token name / `"RRGGBB"` / `null` (keep a multicolor icon's own palette), `card: true` = on a navy rounded card. License + author recorded in the manifest.
- `broll`: a video clip (stock, Hyperframes/brag motion segment, screen recording). `src`, `mode`, `from`, `to`, `src_start` (s into the clip), `fade_in`/`fade_out` (0.15). Any fps/size — conformed to the plan fps and cover-cropped. Clip audio is ignored (voice + music continue). Modes:
  - `full` — full-frame cutaway; the camera is hidden (keep it short, ~1.5–3 s).
  - `full_pip` — full-frame motion/demo with the live camera in a PiP (`pip: {box, crop, radius}`; defaults to the slide PiP). Leave the PiP area empty in the clip.
  - `card` — rounded video card over the camera: `width` (200–1080), `y`, `x`, `radius`; face-checked like any layer.
  Drawn above the camera and below slide/cards/captions. The window may not be longer than the clip after `src_start`. A `<clip>.json` provenance sidecar (stock.py writes one) is copied into the manifest.
- `png`: `src`, `size: [w,h]` — a prepared transparent PNG; or `logo: "<key>"`, `height` — verified logo from `assets/logos/manifest.json`

Hook and CTA text that doesn't fit its card is rejected (shorten it), never clipped.

## `captions`
`y` (center, fraction of height, 0.728), `bridge_gap_s` (0.35), `items: [{"seg", "start", "end", "text", "hl": [exact words to color], "y": optional per-caption center}]`. Text comes from the reviewed transcript, never raw ASR.

## `audio`
`music`: `{"synth": "pad", "gain_db": -17}` or `{"file", "gain_db", "rights_checked": true}`. `sfx`: list of `{"synth": "whoosh" | "chime", "at", "gain_db"}` or `{"file", "rights_checked": true, "at", "gain_db"}` (synth whoosh is seeded → deterministic). `loudnorm`: `{"I": -14, "TP": -1.5, "LRA": 9}`.
