Write `PROMO_PROMPT.md` for "{{context.title}}".

Use the appended inputs named `context` and `worksheet_masked`.

Return Markdown only.

This file belongs to the marketing-assets phase.

Create a downstream image-generation prompt for a square Instagram ad asset that will ultimately be rendered as a `png` or `jpeg`.

The prompt you write must direct the image generator to create:
- a square Instagram image ad at `1080px x 1080px`
- a masked worksheet render with gradient masks as the main subject, not the true worksheet SVG
- a locked landscape `11:8.5` rectangle ratio worksheet image inside the final creative
- a worksheet image that clearly reads as a sheet of paper and stays rectangular

Creative requirements to include in the prompt:
- add direct response headlines, arrows, and other visual attention-grabbing components
- make the headline and download elements eye catching
- include shapes, icons, and typography only
- anchor the graphic in the context of the Content Crusher and visual elements from the Furnace, Forge, and Flame theme
- do not use the word `worksheet` in the creative
- do not include the `SB` number or reference to `week` in any way
- write the creative to be evergreen
- never feature photographic elements, people, or animals
- never include biological elements
- the headline should be based on removing pain or avoiding the challenge that this asset will solve

Source material guidance:
- use the `Choice`, `Promise`, `Frustrations`, and `Action Steps Summary` from the context file as the best source material for pain, stakes, and payoff
- use the masked worksheet as the visual anchor

Output shape:
- `# Asset`
- `# Image Prompt`
- `# Negative Prompt`
- `# Required On-Image Copy`
- `# Visual Checklist`
