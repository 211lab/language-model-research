Write `NEWSLETTER_EMAIL.md` for "{{context.title}}".

Use the appended inputs named `index`, `lesson`, `instructions`, `gpt`, and `context`.

Return Markdown only.

Create an email notification to be sent to students for this week. It should assume the `LESSON` assignment is attached as a PDF file, the worksheet is included, and the weekly contextual essay is linked.

Positioning rules:
- Promote the worksheet as the central execution artifact for the week.
- Frame the lesson, public letter, and GPT coach as support around the worksheet.
- Explain where the worksheet fits inside the reader's broader weekly transformation and system-building process.
- Do not make the email primarily about a 3F component name or component metaphor.
- Use the weekly context to explain why this worksheet matters now and what role it plays in the larger system.

Requirements:
- Give an on-brand subject line.
- Open with a direct lead-in statement.
- Include summary paragraphs of the essay.
- Explain what the student is expected to do with the worksheet.
- Invite the student to read this week's newsletter.
- Invite the student to use the GPT to get the most from the worksheet.
- Finish with encouragement and empowerment.
- Avoid structural lead-in statements.
- Do not use lines like `the central theme is`.

Use the example's job, not its exact wording:
- announce the week cleanly
- frame the weekly problem and why it matters
- tell the student what is inside the packet
- clarify the practical goal for the week
- explain what the worksheet process will produce and where it fits in the larger transformation
- point to the GPT coach
- point to the public letter
- close with force, clarity, and direction

Output shape:
- `## Subject`
- `## Body`
