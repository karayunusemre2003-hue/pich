# Brag-style motion segments inside a talking-head Reel

Launch videos in the style of the /brag skill are built with [Hyperframes](https://github.com/heygen-com/hyperframes)
(HTML + GSAP rendered to video, Apache-2.0). Their strength — animated product UI, counters, charts — is used here as **B-roll inside the speaker's own
video**: the face stays on screen in a PiP while the motion segment explains the numbers. Start from
`examples/motion-template/`.

## Recipe
1. Take the step times from the talking head (`plan_manifest.json` → slide `steps`, or caption times) and make them
   the segment's keyframes, relative to the window start. The segment's length = window length (+0.05 s).
2. Build a Hyperframes composition: `<div id="root" data-composition-id="main" data-width="1080" data-height="1920"
   data-duration="…">`, one `section.clip` with `data-start/data-duration/data-track-index`, a paused GSAP timeline
   registered as `window.__timelines["main"]`. Fonts/icons local inside the composition folder (Manrope is OFL; Iconify SVGs). No audio.
   Leave the PiP region (default box x 584–1024, y 540–1140 — same as the slide PiP) empty — the renderer puts the live camera there.
3. `npx hyperframes check` (0 errors; avoid repeated `fromTo` on one element — use `to` for later changes), then
   `npx hyperframes render --quality high --output ../segment.mp4` (~15 s for 7 s).
4. Plan layer: `{"kind": "broll", "mode": "full_pip", "src": "segment.mp4", "pip": {...}, "from": …, "to": …}`.
5. Music: use a track you hold the rights to (`"rights_checked": true`). Under speech keep drum-heavy tracks around
   -24 dB; qa_reel's masking warning tells you where the music still covers a word.

