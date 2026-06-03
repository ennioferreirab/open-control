# Design Guidelines for Image Generation

## Prompt Engineering

### Structure

Follow this order: **subject → style → composition → lighting → mood → details**.

```
A [subject] in [style], [composition], [lighting], [mood], [details]
```

Example:
```
A minimalist office workspace, flat illustration style, centered composition,
soft natural lighting from the left, calm professional mood, muted earth tones
with one blue accent
```

### Specificity Ladder

| Level | Example | When to use |
|-------|---------|-------------|
| Vague | "a dog" | Never |
| Basic | "a golden retriever sitting on grass" | Quick drafts |
| Detailed | "a golden retriever sitting on a sunlit lawn, soft bokeh background, warm afternoon light, slightly tilted head, photorealistic" | Final output |

### Style Keywords

| Category | Keywords |
|----------|----------|
| Photorealistic | photorealistic, DSLR photo, 35mm film, shallow depth of field, bokeh |
| Illustration | flat illustration, vector art, hand-drawn, watercolor, ink sketch |
| 3D | 3D render, isometric, clay render, low-poly, Blender-style |
| Abstract | geometric abstraction, fluid art, generative art, glitch art |
| Brand | clean, corporate, minimal, modern, professional |

## Photo Editing Prompts

When editing existing images, be explicit about what to change and what to preserve.

### Effective patterns

```
Keep the subject and composition unchanged. Replace the background with [description].
```

```
Adjust the color palette to [warm/cool/muted/vibrant] tones while preserving the original composition.
```

```
Remove [specific element] from the image. Fill the area naturally to match the surrounding context.
```

### Common operations

| Task | Prompt pattern |
|------|---------------|
| Background removal | "Remove the background, make it transparent white" |
| Color correction | "Adjust to warmer tones, increase contrast slightly" |
| Object removal | "Remove the [object] on the right side, fill naturally" |
| Style transfer | "Convert this photo to [watercolor/illustration/pencil sketch] style, preserve the composition" |
| Upscale/enhance | "Enhance detail and sharpness while preserving the original look" |
| Add element | "Add [element] to the [position], matching the existing lighting and style" |

## Composition Principles

### Rule of thirds
Place key elements along the 1/3 and 2/3 grid lines. Specify: "subject positioned at the left third".

### Visual hierarchy
Lead the viewer's eye: large → small, bright → dark, sharp → blurred.

### Negative space
For brand/marketing: leave intentional empty space for text overlay. Specify: "leave the top third empty for text placement".

### Color harmony
- **Complementary**: high contrast, energetic (blue + orange)
- **Analogous**: harmonious, calm (blue + teal + green)
- **Monochromatic**: sophisticated, focused (shades of one hue)

## Aspect Ratios by Use Case

| Use case | Ratio | Notes |
|----------|-------|-------|
| Social post (square) | 1:1 | Instagram, profile images |
| Social story / reel | 9:16 | Instagram stories, TikTok |
| Presentation / hero | 16:9 | Slides, web banners |
| Portrait / poster | 2:3 | Posters, book covers |
| Landscape / banner | 3:2 | Blog headers, landscape photos |
| Tall banner | 1:4 | Vertical web banners |
| Wide banner | 4:1 | Website strips, email headers |

## Quality Checklist

Before delivering a generated image:

1. Does it match the requested subject and style?
2. Are proportions and anatomy correct (faces, hands, text)?
3. Is the aspect ratio appropriate for the intended use?
4. Does the color palette align with the brand or mood?
5. Is there enough resolution for the target medium?
6. Are there artifacts, distortions, or unwanted elements?

If any fail, regenerate with a more specific prompt addressing the issue.
