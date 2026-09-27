# Hero background prompt

`assets/hero_bg.png` (1536x1024, text-free) was generated with Codex's built-in image_gen (variant A of two).
The pich lockup, headline, command chip and meta line are added on top in `index.html` so typography stays crisp.

## Brief given to Codex

```text
Use your built-in image_gen tool to create ONE original hero background for the landing page of "a niche creator app": you drop in a raw talking-head video, the app hands back a finished vertical Reel (cuts, captions, cards, music, checked automatically). Do not create or edit any other files except saving the final PNGs.

File: landscape 3:2 (1536x1024).

Look and feel: a polished consumer app launch visual, like the hero of a design-forward indie app on the App Store — confident, playful, premium, vivid. NOT a dark enterprise dashboard.

Scene (RIGHT 55% only): a sleek generic smartphone standing slightly tilted, its screen showing a vivid vertical video frame made of pure shapes: soft abstract gradient scene, two blank rounded caption bars (one white, one warm yellow #FFD64D), a small blank rounded card near the top. Beside/behind it, a short stack of raw clip tiles (plain translucent rectangles with blurred color) visibly getting "cleaned up": the tiles on the left are rough and uneven, the ones touching the phone are crisp and aligned. A few floating glossy 3D elements in the brand palette — a small rounded play-button pebble, a soft sparkle, a rounded checkmark badge shape, a tiny waveform ribbon — arranged with generous spacing, like objects orbiting the phone.

Background: a smooth vivid gradient from electric blue (#3B5BFF) through indigo (#5B45FF) to violet (#9A3FFF), with soft light blooms and subtle depth; the LEFT 45% stays calm and uncluttered (smooth gradient only, slightly darker toward the left edge) because a logo and headline will sit there. Keep every important element between y=90 and y=934 (crop-safe to 2:1) and 60 px from the right edge.

Style: glossy soft 3D, rounded forms, frosted glass and satin plastic, gentle studio lighting with soft shadows, crisp and clean, high contrast between the white/yellow elements and the violet-blue background.

Hard constraints: NO text, letters, numbers, words, logos, brand marks, watermarks, app-store badges, readable UI, status bars, notches or dynamic islands; NO people, faces, hands or human silhouettes anywhere (including on the screen); the phone is fully generic.

Make 2 variants with different compositions. Inspect each; if one has letters/text-like marks, a face or a logo, regenerate it once. Save them in the current directory as hero_bg_a.png and hero_bg_b.png. Finally print, for each: file path, the exact prompt you sent to image_gen, and the original generated_images path.
```

## Codex output (exact image_gen prompts)

### Variant A



Exact final prompt:

```text
Use case: stylized-concept
Asset type: original landing-page hero background for a niche consumer creator app
Output canvas: exactly 1536 x 1024 pixels, landscape 3:2.

Scene/backdrop: A smooth vivid full-bleed gradient flowing from electric blue #3B5BFF through indigo #5B45FF to violet #9A3FFF, with soft diffused light blooms, subtle depth, and a slightly darker left edge. The entire LEFT 45% of the canvas, x=0 through x=691, must be calm, smooth, empty gradient only. Absolutely no object, tile, particle, shadow, floor reflection, distinct glow blob, or visual clutter may enter x<720; reserve that space for a logo and headline.

Subject and composition: Deliberately inset the full composition inside a strict invisible safe box from x=740 to x=1400 and y=140 to y=880. No visible pixel of any object, tile, accent, shadow, or reflection may extend outside that box. A sleek fully generic smartphone stands prominently around x=1100, slightly tilted clockwise in three-quarter view, with a thin rounded satin-plastic frame and a clean full-bleed display. No notch, camera cutout, dynamic island, speaker slot, buttons, status bar, or manufacturer detail. The phone screen shows a vivid abstract vertical-video composition made only from pure nonfigurative shapes: a soft coral-to-cyan gradient scene, exactly two completely blank rounded caption bars in the lower half (one solid white, one warm yellow #FFD64D), and one small completely blank frosted rounded card near the top. Every bar and card is an empty geometric shape with no glyphs, strokes, icons, or markings.

Behind and just left of the phone, show a short diagonal stack of raw clip tiles progressing toward the device. Start the first tile no farther left than x=740. The far-left tiles are plain translucent frosted rectangles with softly blurred color, slightly rough, irregular, and unevenly spaced; the tiles touching the phone become crisp, straight, evenly aligned, and polished. Keep this transformation visual and abstract, with no arrows, labels, controls, timelines, or interface symbols.

Add only four widely spaced glossy 3D accents orbiting close to the phone, all fully inside x=780..1380 and y=160..850: a small rounded triangular play-button pebble, a soft four-point sparkle, a rounded checkmark badge shape, and a tiny curved waveform ribbon. Use white, warm yellow #FFD64D, pale cyan, and violet accents. Keep them airy and secondary. Leave a conspicuously wide empty margin of at least 136 pixels between every object and the right canvas edge.

Style/medium: polished design-forward indie App Store launch visual; confident, playful, premium, vivid; glossy soft 3D rendering; rounded forms; frosted glass and satin plastic; gentle studio lighting; soft contact shadows; crisp clean edges; strong white/yellow contrast against violet-blue. This is a joyful consumer app visual, never a dark enterprise dashboard.

Spatial constraints: all important objects and every visible part of their shadows/reflections must be within x=740..1400 and y=140..880. The left 45% must remain smooth gradient only. The rightmost 136 pixels must remain empty gradient only. This also keeps everything safely within y=90..934 for a centered 2:1 crop.

Hard constraints: NO text, letters, numbers, words, typographic marks, logos, brand marks, watermarks, signatures, app-store badges, readable UI, fake UI labels, status bars, notches, dynamic islands, people, faces, eyes, heads, bodies, hands, skin, human silhouettes, portraits, avatars, or character-like forms anywhere, including on the phone screen. The smartphone must be fully generic.
```

### Variant B



Exact final prompt:

```text
Use case: stylized-concept
Asset type: original landing-page hero background for a niche consumer creator app
Output canvas: exactly 1536 x 1024 pixels, landscape 3:2.

Scene/backdrop: A smooth vivid full-bleed gradient flowing from electric blue #3B5BFF through indigo #5B45FF to violet #9A3FFF, with broad soft light blooms, subtle atmospheric depth, and a slightly darker left edge. The entire LEFT 45% of the canvas, x=0 through x=691, must be calm, smooth, empty gradient only. Absolutely no object, tile, particle, shadow, floor reflection, distinct glow blob, or visual clutter may enter x<720; reserve that space for a logo and headline.

Subject and composition: Deliberately inset the full composition inside a strict invisible safe box from x=740 to x=1400 and y=140 to y=880. No visible pixel of any object, tile, accent, shadow, or reflection may extend outside that box. Create a composition distinct from a standard centered phone: a sleek fully generic smartphone sits around x=1120 and slightly lower, standing in three-quarter view and tilted gently counterclockwise, with a slim rounded satin-plastic frame and clean full-bleed display. No notch, camera cutout, dynamic island, speaker slot, buttons, status bar, or manufacturer detail. The screen shows a vivid abstract vertical-video frame made only of pure nonfigurative shapes: a soft aqua-to-coral gradient scene, exactly two completely blank rounded caption bars staggered near the bottom (one solid white, one warm yellow #FFD64D), and one small completely blank rounded frosted card near the top. Every bar and card is an empty geometric block with no glyphs, strokes, icons, or markings.

Behind the phone, arrange a compact stepped fan of raw clip tiles sweeping upward from the lower-left toward the device. Start the outermost tile no farther left than x=740. The outer tiles are translucent frosted rectangles with blurred color, subtly skewed and uneven; as the fan meets the phone, the rectangles become sharp, perfectly squared, evenly spaced, and aligned. The visual should imply automatic cleanup through order and finish alone. No arrows, labels, controls, timelines, or interface symbols.

Add only four generously spaced glossy 3D accents arranged asymmetrically but kept close to the phone, all fully inside x=780..1380 and y=160..850: a small rounded triangular play-button pebble near the upper-right, a soft four-point sparkle above-left of the phone, a rounded checkmark badge shape near the lower-right, and a tiny floating waveform ribbon near the lower-left. Use white, warm yellow #FFD64D, pale cyan, and violet accents. Keep the objects sparse, floating, and secondary. Leave a conspicuously wide empty margin of at least 136 pixels between every object and the right canvas edge.

Style/medium: polished design-forward indie App Store launch visual; confident, playful, premium, vivid; glossy soft 3D rendering; rounded forms; frosted glass and satin plastic; gentle studio lighting; soft shadows; crisp clean edges; strong white/yellow contrast against violet-blue. Joyful consumer app aesthetic, never a dark enterprise dashboard.

Spatial constraints: all important objects and every visible part of their shadows/reflections must be within x=740..1400 and y=140..880. The left 45% must remain smooth gradient only. The rightmost 136 pixels must remain empty gradient only. This also keeps everything safely within y=90..934 for a centered 2:1 crop.

Hard constraints: NO text, letters, numbers, words, typographic marks, logos, brand marks, watermarks, signatures, app-store badges, readable UI, fake UI labels, status bars, notches, dynamic islands, people, faces, eyes, heads, bodies, hands, skin, human silhouettes, portraits, avatars, or character-like forms anywhere, including on the phone screen. The smartphone must be fully generic.
```
