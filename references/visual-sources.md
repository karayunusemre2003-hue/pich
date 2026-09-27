# Visual sources — which image for which spoken idea (Faz 3)

Design system: `assets/design/default.json` (tokens, layout zones, estimated Instagram UI zones). A plan picks it with `"design": "default"` (default); plan `tokens` override single colors.

| Spoken content | Source | Layer |
|---|---|---|
| Brand / model name | **Verified logo library** `assets/logos/manifest.json` (file + official `source_url` + `verified_at`). Not in the library → plain text, or add it after checking the official press kit. | `{"kind": "png", "logo": "claude", "height": 96, "y": …}` |
| Link / handle | Literal text the speaker said, verified | `hook_card` / `cta_card` text, never an image |
| Small UI symbol (bell, check, arrow, emoji) | Iconify, 200k+ open icons, no key — prefer Lucide / Tabler / Material (MIT/ISC/Apache); each render records collection license + author | `{"kind": "icon", "icon": "lucide:bell", "card": true}` |
| 2–4 step process | Stepper slide (`slide`) — drawn icons, editable labels | `slide.steps` |
| Abstract idea | Codex `image_gen` concept art, letterless (template below) or a drawn icon | `image_card` (`provenance: "image_gen"`) |
| Real-world scene (market, office, city) | Pexels photo via `python3 scripts/stock.py search/sheet/get` — sidecar JSON with author + license; no people/brands shown as endorsing anything | `image_card` (`provenance: "stock"`) |
| Numbers / proof | Real source only; editable type | `png` prepared from data, cite it in the manifest |

Logo library: the repo ships none. Build yours with `scripts/fetch_logos.py` — Simple Icons slugs (`python3 scripts/fetch_logos.py claude github youtube`) give `<slug>` (brand color) and `<slug>-white` (for dark backgrounds); `--brandfetch DOMAIN SLUG` (env `BRANDFETCH_API_KEY`) adds brands missing there, only when the brand owner has claimed the Brandfetch profile. Or add a file by hand from the brand's own press page with `{"file", "source_url", "verified_at", "notes"}` — the renderer refuses a key without them. `PICH_LOGOS_DIR` points to a library outside the skill folder.

Safe zones: keep hooks/CTAs below ~220 px from the top and above the bottom 450 px, clear of the right 120 px in the lower half (`ig_ui_estimate` in the design preset; qa_reel warns). 

## image_gen prompt template (letterless concept card)

```
Minimal premium editorial illustration for a vertical Instagram Reel popup card.
Concept: <one idea from the sentence, e.g. "an AI assistant orchestrating several tools at once">.
Style: soft 3D / clay render, deep navy background (#141821) with electric blue (#2F5BFF) and warm yellow (#FFD64D) accents, gentle rim light, clean negative space.
Composition: single clear subject, centered, readable at 520 px width, 16:9.
Absolutely no text, letters, numbers, logos, UI screenshots, watermarks or human faces.
```

Check the output before use: no pseudo-letters, no brand look-alikes, subject readable at phone size. Record prompt + file in the project's manifest (`provenance: "image_gen"`).

## Transitions / outro

Transitions are deliberately simple: hard speech cuts, per-segment punch-in (`edl[].zoom` 1.06), whoosh on slide in/out, chime under the CTA tail. The outro is the `cta_card` on a quiet tail segment (`volume` 0.35). Add new transition types only when a real Reel needs one.
