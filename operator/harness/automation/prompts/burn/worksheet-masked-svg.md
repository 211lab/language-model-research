Design `WORKSHEET_MASKED.svg` for "{{context.title}}".

Use the appended input named `worksheet`.

Return a complete raw SVG document only. Do not wrap it in a code block.

Generate a new SVG by preserving the worksheet's exact page size, coordinates, geometry, class system, and element layout.

Hard constraints:
- Preserve the exact `1100 x 850` page and full-page composition.
- Preserve the exact layout, positions, sizing, and box structure of the source worksheet.
- Preserve the XML declaration and SVG root structure.
- Preserve the title block in place.
- Preserve the model letters in place.
- Preserve each letter box or letter marker in place.
- Preserve every model letter marker from the source worksheet, including repeated letters.
- Preserve the overall "full worksheet page" appearance. Do not collapse the page into fragments or sparse blocks.
- The masked file must inherit whatever creative structure the main worksheet used.
- Do not normalize or simplify the source worksheet layout.

Masking rules:
- Replace all explanatory copy, helper copy, instructions, prompts, summaries, and fillable guidance with censor blocks.
- Use only light grayscale tones for the censor blocks.
- Vary the grayscale tones slightly so the page reads like a masked form or heat-map document.
- Keep the title readable.
- Keep the model letters readable.
- Everything else should be reduced to abstract masked bars, blocks, or lines that follow the original geometry.

Do not:
- move elements
- resize the layout
- simplify the worksheet into a poster
- reinterpret the structure
- create a new arrangement from the topic or verb
- add new decorations, icons, gradients, colors, or textures
- output anything except the SVG document

The result should look like the exact same worksheet template with the internal instructional content censored, while still clearly reading as a complete full-page worksheet.
