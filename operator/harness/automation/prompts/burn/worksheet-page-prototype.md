Write `WORKSHEET_PAGE.md` for "{{context.title}}".

Use the appended inputs named `context`, `page_copy`, and `promo`.

Return Markdown only.

Create a Hugo content prototype in exactly this format and structure:

```yaml
---
title: Stop Losing Ground
url: /letters/the-furnace-that-refuses-to-go-out/worksheet/
layout: worksheet
hideHeader: true
hideFooter: true
hiddenInHomeList: true
hiddenInList: true
hideSummary: true
hideMeta: true
disableShare: true
build:
  render: always
  list: never
worksheet:
  image-wrap:
    hero-image:
      src: "../promo.png"
      alt: "Forged tactical paper artifact with dark furnace lighting"
  copy:
    eyebrow: "Pressure Into Proof"
    hero-title: "Stop Losing Ground When Life Gets Heavy"
    subhead: "Build a clear plan that keeps you steady when stress hits and focus breaks."
    benefits:
      - "Know what to do next when your mind feels crowded."
      - "Stay with the goal when pressure tries to pull you off track."
      - "Turn hard days into proof that you can finish."
    form:
      input:
        type: email
        name: email
        placeholder: "Enter your email"
        aria-label: "Email address"
        required: true
      button:
        type: submit
        text: "Get The Plan"
    microcopy: "Free download. Instant access."
---
```

Requirements:
- Output only the frontmatter prototype file.
- Keep the same field order and nesting shown above.
- Set the `url` using the current letter slug: `/letters/{{context.slug}}/worksheet/`
- Use `../promo.png` as the hero image source.
- Keep the alt text aligned with the furnace/forge/tactical artifact visual language.
- Use the page-copy and context inputs to choose the strongest eyebrow, hero title, subhead, and three benefits.
- Keep the copy direct, dream-outcome driven, and easy to scan.
- Use exactly 3 benefits.
- Keep `microcopy` exactly: `Free download. Instant access.`
