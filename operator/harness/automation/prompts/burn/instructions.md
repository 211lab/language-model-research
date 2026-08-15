Write `INSTRUCTIONS.md` for "{{context.title}}".

Use the appended inputs named `lesson`, `context`, and `seed`.

Return Markdown only.

Write a long form process, with an introduction related to the lesson, for the student to follow while filling out the worksheet that follows this guided exercise through each letter of the process from the content crusher model.

Model source of truth:
- Treat `context` as the binding source for the worksheet process.
- Extract the exact `## Actionable VERB` and the complete `## Model` from `context`.
- Use every model letter and step from `context`, in the same order.
- Do not rename, replace, combine, summarize, or skip any model letter.
- Do not use the three-step `Action Steps Summary` as the worksheet process.
- If `lesson`, `brief`, and `context` disagree about the action model, `context` wins.

Write the instructions in lecture form, in second person, guiding the reader to get the most value out of the worksheet one letter at a time.

Requirements:
- Start with an introduction tied directly to the lesson's main tension, truth, and desired outcome.
- Follow the exact model one letter at a time in the same order used in `context`.
- Give clear directions on how to fill out each section of the worksheet.
- For each step, include bullet examples of:
  - what to avoid in the answer,
  - what works better in the answer.
- Keep each section anchored to the specific model step for that letter.
- Do not use procedural lead-in comments or navigation phrases such as `Open the first section of the worksheet`, `Proceed to the third section`, `Next, move to`, or similar stage-direction wording.
- Write each section as direct instruction about the work itself, not commentary about where the reader is in the document.
- Keep the tone direct, practical, and instructional.
- Push toward specificity, honesty, and usable answers.
- Do not drift into generic motivation or abstract reflection.
- Make each step help the student complete the worksheet, not merely think about it.

Suggested shape:
- Introduction
- One section per model letter from the `## Model` in `context`
- Closing push to finish the worksheet and act on what was written
