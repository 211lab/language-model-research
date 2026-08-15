# Burn Generation Prompts

These prompt templates are used by the composable burn pipeline.

Each template is called through the pipeline harness, which adds shared instructions
that require final output only:

- Markdown templates must return Markdown only.
- SVG templates must return a complete `<svg>` document only.
- No reasoning, status text, or code fences should be included.

Templates can also reference runtime values with `{{...}}`, including:

- `{{context.title}}`
- `{{context.slug}}`
- `{{context.date}}`
- `{{variables.voice}}`
- `{{current_step.output_path}}`

Step inputs are appended to the prompt under their aliases, so later prompts can
read the output of earlier prompts without manual copy/paste.
