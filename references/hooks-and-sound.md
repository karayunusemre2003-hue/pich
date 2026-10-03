# Hooks, sound cues and generated-shot prompts

Craft rules for steps 3–5. They decide *what* to put in the plan; the schema in [render-reel-plan](render-reel-plan.md) decides *how*.

## Hook variants (step 5)

Write three hook cards for every video, one of each type, all from the video's own claim (never invent a result):

| Type | What it does | Example shape |
|---|---|---|
| Warning | names a mistake the viewer is making | "Bunu yapıyorsan para kaybediyorsun" |
| Result | shows the outcome first, explains after | "3 günde 40 randevu: nasıl" |
| Curiosity | opens a question the video answers | "Kimsenin bakmadığı ayar" |

Sentence templates that work as hooks:

- "What if I told you I got X by doing Y?"
- "I'm an X, of course I don't do Y."
- "If you're trying to do X, is Y or Z better?"

Put all three in `variants.json` and render them with `hook_variants.py`. The cheapest live test is Instagram Trial Reels: post the three versions as trials, wait 24 h, publish the winner to the main grid. Posting is the user's call; the agent only prepares the three files.

## Reading the numbers after posting

| Symptom | Likely cause | Fix in the next cut |
|---|---|---|
| Low watch time / early swipe | weak hook | show the result in the first frame, start with the claim, cut the greeting |
| Watched but few shares | weak or early CTA | move the CTA to the tail, make it specific ("send this to someone who …") |
| Drop in the middle | value given too early, then nothing new | say why it matters before the payoff; add a re-hook (question or scene change) |

## Sound cues (`sfx`)

One cue per visual event, never a cue without an event. Keep cues under the voice (start at `gain_db` -12 and listen).

| Visual event | Cue |
|---|---|
| zoom in/out, B-roll cut in, slide entrance | whoosh |
| card, icon or popup appearing | short pop / click |
| build-up before a number or reveal | riser (ends on the reveal frame) |
| hard transition between sections | camera shutter |
| final reveal / CTA | soft chime |

Built in: `{"synth": "whoosh"}` and `{"synth": "chime"}`. Anything else must be a file you have the rights to, marked `"rights_checked": true`.

## Prompting generated shots (B-roll, motion references)

For video models (Veo, Kling, Seedance, Wan …) write the prompt in this order:

1. **Camera:** angle, lens in mm, movement and what it moves along ("35 mm, slow dolly-in on a slider, eye level").
2. **Time and place:** time of day, location, atmosphere, weather if it matters.
3. **Subject:** who is in frame, what they do, where they look, and where they are in the next seconds relative to the camera.

The more precise point 3 is, the closer the shot. For a specific action, generate a start frame and an end frame as images first and give both to the video model.

When a shot or ad style works, save its prompt as JSON and reuse it: change only the product/subject fields and keep camera, light and motion the same. Same for illustration styles: turn a reference image into a JSON style prompt once, then swap only the object.
