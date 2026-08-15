Design `WORKSHEET.svg` for "{{context.title}}".

Use the appended input named `instructions`.

Return a complete raw SVG document only. Do not wrap it in a code block.

This prompt must adhere strictly to the SVG document standard shown below. Do not loosely imitate it.

The SVG file format, page size, typography classes, and full-page worksheet intent are fixed.
The internal worksheet layout is not fixed.

Model source of truth:
- Treat `instructions` as the binding source for the worksheet process.
- Extract the exact named steps and their order from `instructions`.
- Every process step must receive its own actionable fillable area.
- Do not rename, replace, combine, summarize, or skip any process step.

The model has full creative authority to adapt the internal worksheet composition to the chosen verb and process.
That includes:
- changing the number of content blocks
- changing the layout order
- changing the arrangement of the process sections
- changing how the process is distributed across the page
- changing the final reflection and footer structure
- changing how fillable areas are shaped

The design must still read clearly as a complete full-page printable worksheet.

Hard constraints:
- Output a full-page worksheet only.
- Use exactly `width="1100"` and `height="850"`.
- Use exactly `viewBox="0 0 1100 850"`.
- Use a white background.
- Start with the XML declaration, then the `<svg>` root.
- Include `<title>`, `<desc>`, `<defs>`, `<style>`, and background `<rect>`.
- Fill the page vertically and horizontally like the reference example. Do not generate a partial layout, floating fragments, or sparse composition.
- Keep all elements inside page bounds.
- Keep every box rectangular and aligned.
- Keep the worksheet printable and usable by hand.
- Keep the same CSS class names used in the example.
- Keep the same overall visual style: black strokes, grayscale helper lines, white boxes, Arial/Helvetica stack.
- Keep the same overall production quality and SVG discipline as the reference structure.

Content mapping requirements:
- Use the actual SteadyBurn number if it is available from the inputs. If not, use `SBXX`.
- Use the topic as the large title.
- Use a concise process framing as the subtitle.
- Use the first process step as the top-right intro box when appropriate.
- Use the named process as the large centered heading.
- Use the full process steps from `instructions` as the primary driver of the worksheet architecture.
- The number of content blocks must expand or contract to fit the full process.
- The order of blocks may change if the process becomes clearer that way.
- The footer structure may change if the content needs a different closing pattern.
- Use short box labels, one short instruction line, one short helper line, and clear fillable lines or numbered slots where appropriate.
- Make the fillable structure feel intentional and useful for the specific verb, not generic.

Structure requirements:
- Keep the root element formatting close to the reference.
- Keep the same class definitions unless a minimal wording update is required in `title` or `desc`.
- Keep a single background rectangle.
- Keep a strong title zone, a clear model zone, and a clear fillable zone.
- Keep the layout balanced across the whole page.
- Use enough content blocks and fillable regions to make the page feel complete.
- Preserve visual hierarchy and generous writing space.

Do not:
- compress the design into a poster or card
- change the page ratio
- output a sparse or unfinished worksheet
- abandon the worksheet function in favor of decoration
- use decorative illustration, gradients, icons, photos, textures, shadows, or colors beyond grayscale/black
- output prose before or after the SVG

Creative authority rule:
- You may redesign the internal worksheet composition completely for each new process.
- You may change block count, order, and grouping only if every process step remains visible and has its own fillable area.
- You may make the page asymmetrical, modular, linear, radial, laddered, or staged if it still prints cleanly and remains easy to fill out by hand.
- Creativity is encouraged inside the page. Sloppiness is not.

Use this exact format pattern as the required structural reference:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="850" viewBox="0 0 1100 850" role="img" aria-labelledby="title desc">
  <title id="title">SB27 Worksheet, Belief Systems Check</title>
  <desc id="desc">Landscape worksheet on a white background with large title, introduction, fillable sections built around the REFINE action model, and a three step summary footer.</desc>

  <defs>
    <style>
      .bg { fill: #ffffff; }
      .line { stroke: #111111; stroke-width: 2; fill: none; }
      .soft { stroke: #777777; stroke-width: 1.2; fill: none; }
      .box { fill: #ffffff; stroke: #111111; stroke-width: 2; rx: 18; ry: 18; }
      .mini { fill: #ffffff; stroke: #111111; stroke-width: 1.5; rx: 12; ry: 12; }
      .label { font-family: Arial, Helvetica, sans-serif; font-size: 13px; font-weight: 700; fill: #111111; }
      .small { font-family: Arial, Helvetica, sans-serif; font-size: 11px; fill: #111111; }
      .tiny { font-family: Arial, Helvetica, sans-serif; font-size: 9px; fill: #111111; }
      .title { font-family: Arial, Helvetica, sans-serif; font-size: 28px; font-weight: 700; fill: #111111; }
      .sub { font-family: Arial, Helvetica, sans-serif; font-size: 16px; font-weight: 700; fill: #111111; }
      .verb { font-family: Arial, Helvetica, sans-serif; font-size: 30px; font-weight: 700; fill: #111111; letter-spacing: 2px; }
      .letter { font-family: Arial, Helvetica, sans-serif; font-size: 34px; font-weight: 700; fill: #111111; }
      .num { font-family: Arial, Helvetica, sans-serif; font-size: 24px; font-weight: 700; fill: #111111; }
      .fillline { stroke: #9a9a9a; stroke-width: 1; }
      .dot { fill: #111111; }
    </style>
  </defs>

  <rect class="bg" x="0" y="0" width="1100" height="850"/>

  <text class="tiny" x="40" y="34">SB27</text>
  <text class="title" x="40" y="70">BELIEF SYSTEMS CHECK</text>
  <text class="sub" x="40" y="96">Challenge Your Assumptions</text>

  <rect class="mini" x="700" y="34" width="360" height="78"/>
  <text class="label" x="720" y="58">CHOICE</text>
  <text class="small" x="720" y="78">Keep obeying old stories and old limits, or put</text>
  <text class="small" x="720" y="94">one belief on trial and prove a stronger one.</text>

  <text class="verb" x="444" y="142">REFINE</text>
  <line class="line" x1="40" y1="154" x2="1060" y2="154"/>

  <rect class="box" x="40" y="180" width="320" height="185"/>
  <text class="letter" x="60" y="222">R</text>
  <text class="label" x="105" y="204">REVEAL THE BELIEF</text>
  <text class="small" x="105" y="224">Write the exact sentence your mind repeats.</text>
  <text class="tiny" x="105" y="242">Avoid vague words. Name the belief plainly.</text>
  <line class="fillline" x1="60" y1="270" x2="330" y2="270"/>
  <line class="fillline" x1="60" y1="300" x2="330" y2="300"/>
  <line class="fillline" x1="60" y1="330" x2="330" y2="330"/>

  <rect class="box" x="390" y="180" width="320" height="185"/>
  <text class="letter" x="410" y="222">E</text>
  <text class="label" x="455" y="204">EXAMINE THE SOURCE</text>
  <text class="small" x="455" y="224">Trace where this belief first felt true.</text>
  <text class="tiny" x="455" y="242">Person, event, failure, family pattern, or season.</text>
  <line class="fillline" x1="410" y1="270" x2="680" y2="270"/>
  <line class="fillline" x1="410" y1="300" x2="680" y2="300"/>
  <line class="fillline" x1="410" y1="330" x2="680" y2="330"/>

  <rect class="box" x="740" y="180" width="320" height="185"/>
  <text class="letter" x="760" y="222">F</text>
  <text class="label" x="805" y="204">FIND COUNTEREVIDENCE</text>
  <text class="small" x="805" y="224">List facts that prove the old belief is not final.</text>
  <text class="tiny" x="805" y="242">Small proof still counts.</text>
  <text class="tiny" x="760" y="268">1.</text><line class="fillline" x1="780" y1="268" x2="1030" y2="268"/>
  <text class="tiny" x="760" y="292">2.</text><line class="fillline" x1="780" y1="292" x2="1030" y2="292"/>
  <text class="tiny" x="760" y="316">3.</text><line class="fillline" x1="780" y1="316" x2="1030" y2="316"/>
  <text class="tiny" x="760" y="340">4.</text><line class="fillline" x1="780" y1="340" x2="1030" y2="340"/>

  <rect class="box" x="40" y="395" width="320" height="185"/>
  <text class="letter" x="60" y="437">I</text>
  <text class="label" x="105" y="419">INSTALL A BETTER BELIEF</text>
  <text class="small" x="105" y="439">Write a stronger belief you can act on.</text>
  <text class="tiny" x="105" y="457">No fake hype. Make it believable and useful.</text>
  <line class="fillline" x1="60" y1="485" x2="330" y2="485"/>
  <line class="fillline" x1="60" y1="515" x2="330" y2="515"/>
  <line class="fillline" x1="60" y1="545" x2="330" y2="545"/>

  <rect class="box" x="390" y="395" width="320" height="185"/>
  <text class="letter" x="410" y="437">N</text>
  <text class="label" x="455" y="419">NAVIGATE ONE REAL TEST</text>
  <text class="small" x="455" y="439">Choose one action this week to prove it.</text>
  <text class="tiny" x="455" y="457">Include what, when, and proof of completion.</text>
  <text class="tiny" x="410" y="485">What:</text><line class="fillline" x1="455" y1="485" x2="680" y2="485"/>
  <text class="tiny" x="410" y="515">When:</text><line class="fillline" x1="455" y1="515" x2="680" y2="515"/>
  <text class="tiny" x="410" y="545">Proof:</text><line class="fillline" x1="455" y1="545" x2="680" y2="545"/>

  <rect class="box" x="740" y="395" width="320" height="185"/>
  <text class="letter" x="760" y="437">E</text>
  <text class="label" x="805" y="419">EVALUATE THE PROOF</text>
  <text class="small" x="805" y="439">Record what happened after you acted.</text>
  <text class="tiny" x="805" y="457">Turn the result into evidence.</text>
  <line class="fillline" x1="760" y1="485" x2="1030" y2="485"/>
  <line class="fillline" x1="760" y1="515" x2="1030" y2="515"/>
  <line class="fillline" x1="760" y1="545" x2="1030" y2="545"/>

  <rect class="mini" x="40" y="610" width="1020" height="88"/>
  <text class="label" x="60" y="636">FINAL COMMAND</text>
  <text class="small" x="60" y="660">The old belief was not the full truth. The new belief I will keep practicing is:</text>
  <line class="fillline" x1="60" y1="684" x2="1030" y2="684"/>

  <rect class="mini" x="40" y="725" width="315" height="82"/>
  <text class="num" x="60" y="760">1</text>
  <text class="label" x="95" y="748">NAME IT</text>
  <text class="tiny" x="95" y="768">Write the limiting belief in one clear sentence.</text>
  <text class="tiny" x="95" y="784">Stop fighting a shadow.</text>

  <rect class="mini" x="392" y="725" width="315" height="82"/>
  <text class="num" x="412" y="760">2</text>
  <text class="label" x="447" y="748">TEST IT</text>
  <text class="tiny" x="447" y="768">Gather facts against the belief.</text>
  <text class="tiny" x="447" y="784">Expose where it has exaggerated reality.</text>

  <rect class="mini" x="745" y="725" width="315" height="82"/>
  <text class="num" x="765" y="760">3</text>
  <text class="label" x="800" y="748">PROVE IT</text>
  <text class="tiny" x="800" y="768">Take one action that supports the new belief.</text>
  <text class="tiny" x="800" y="784">Turn thought into identity.</text>
</svg>
```
