# Hero background prompt

`assets/hero_bg.png` (1536x1024, text-free) was generated with Codex's built-in image_gen (variant B of two).
The title, tagline, chips and logo are added on top in `index.html` so the typography stays crisp.

## Brief given to Codex

```text
Use your built-in image_gen tool (load the .system/imagegen skill first) to create ONE original hero image for the README of an open-source tool that turns a raw talking-head video into a finished vertical social-media Reel, with an AI editor and automatic quality checks. Do not create or edit any other files except saving the final PNG(s).

File name: hero_bg.png — landscape 3:2 (1536x1024).

Concept / story: raw footage becomes a polished vertical video. On the RIGHT half: a sleek modern smartphone, floating at a slight 3/4 angle, its screen glowing with a vertical video frame (abstract soft gradient scene with a few blank rounded caption bars and small blank glass cards — pure shapes, nothing readable). From the lower left toward the phone flows a curved ribbon of raw film/timeline clips (plain translucent rectangular frames with soft color gradients) being precisely cut by thin beams of light; the pieces reassemble cleanly as they enter the phone. Around the phone: a few floating frosted-glass panels (blank), a smooth audio waveform ribbon, and small glowing dots suggesting precision and checking.

Composition: the LEFT 45% of the image must be calm, dark, nearly empty negative space (smooth deep-navy gradient with a very subtle glow) — a title will be placed there later. Main subject weighted to the right third, strong readable silhouette, generous margins, nothing important within 60 px of the edges. Crop-safe to 2:1 (top and bottom 85 px may be cut).

Style: premium high-end 3D product render, cinematic, soft volumetric light, glass and satin materials, shallow depth of field, elegant and modern, like a flagship product launch keynote visual.

Palette: deep midnight navy (#0E1424 to #1B2440) background, electric blue (#2F5BFF) glow, icy cyan (#78D6FF) highlights, a few warm yellow (#FFD64D) accents on the caption bars and one light beam. High contrast, not muddy.

Hard constraints: ABSOLUTELY NO text, letters, numbers, words, logos, brand marks, watermarks, app icons, readable UI, fake code, and NO people, faces or human silhouettes anywhere (including on the phone screen). The phone must be generic (no brand, no camera-bump branding).

Make 2 variants with different compositions. Inspect each: if any contains letters/text-like marks, a face, or a brand logo, regenerate that one once. Save the chosen PNGs into the current directory as hero_bg_a.png and hero_bg_b.png. Finally print, for each: file path, the exact prompt you sent to image_gen, and the original generated_images path.
```

## Exact prompt Codex sent to image_gen

```text
Create ONE original README hero background image, exactly 1536x1024 pixels, landscape 3:2, for an open-source AI tool that transforms raw talking-head footage into a polished vertical social-media Reel using an AI editor and automatic quality checks. Depict the transformation without showing any person or face. Render it as a premium high-end 3D product-launch visual: cinematic, minimalist, elegant, soft volumetric illumination, frosted glass, satin metal, refined reflections, and shallow depth of field.

COMPOSITION: the LEFT 45 percent must remain almost completely empty and title-safe: an uninterrupted deep-midnight-navy gradient from #0E1424 to #1B2440 with one extremely subtle atmospheric glow and no floating objects. On the RIGHT half, place a sleek generic unbranded smartphone in a distinctly dynamic diagonal composition: floating slightly lower than center, rotated clockwise in a three-quarter perspective, with its top receding into depth and its glowing screen facing toward the empty left side. Keep the entire phone at least 60 pixels from all canvas edges and give it a strong readable silhouette. On the screen show only an abstract vertical-video frame: a smooth electric-blue-to-icy-cyan gradient field, several large solid blank rounded bars with two small warm-yellow #FFD64D accents, and a few blank translucent glass tiles. Every element is a pure featureless geometric shape, not a readable interface.

STORY AND MOTION: a thin ribbon of raw clip frames emerges from the lower-left direction but hugs the lower-middle corridor so the title area stays calm. It arcs upward BEHIND the phone in one broad C-shaped sweep, then curls forward and enters the lower side of the screen. The source frames are sparse translucent rectangles containing only blurred color gradients, without film perforations or thumbnails. Along the right-center transformation zone, several razor-thin icy-cyan light planes and exactly one warm-yellow beam slice the strip with geometric precision; fragments separate briefly, then snap into a clean aligned stack immediately before entering the phone. Add a single smooth audio-waveform ribbon orbiting behind the phone, three asymmetrically placed blank frosted-glass panels confined to the rightmost half, and a small ordered trail of glowing dots that implies automated checking and successful precision. Use depth, overlap, and controlled motion blur for a distinct circular-flow composition.

PALETTE AND FINISH: deep navy #0E1424 to #1B2440 background, electric blue #2F5BFF, icy cyan #78D6FF, minimal warm yellow #FFD64D. Crisp high contrast with localized glow, rich blacks, clean material separation, never murky. Flagship keynote render quality with polished glass and satin surfaces, generous margins, no clutter. Make it crop-safe to 2:1: keep all essential content between y=85 pixels and y=939 pixels, with no important element in the top or bottom 85 pixels. No border or poster frame.

ABSOLUTE HARD CONSTRAINTS: NO text, NO letters, NO numbers, NO words, NO logos, NO brand marks, NO watermarks, NO signatures, NO app icons, NO symbols, NO fake code, NO readable captions, NO readable UI, NO status bar, NO clock, NO battery or signal marks, NO camera interface, NO text-like microdetails, and NO typographic shapes. NO people, NO faces, NO eyes, NO heads, NO bodies, NO hands, and NO human silhouettes anywhere, including reflections and the phone screen. The phone must be fully generic and brandless, with no logo, no recognizable camera-bump branding, no notch, and no dynamic-island shape. Avoid any shape that could be mistaken for a character or logo.
```
