Write `CONTEXT.md` for "{{context.title}}".

Use the appended input named `seed`.

If there is no topic provided directly in this prompt, use existing content from the inputs above and start your response by referencing what topic is being discussed first.

Return Markdown only.

Developed model registry:
{{registry.entries_markdown}}

Hard constraints:
- Choose a brand new `Actionable VERB` and model name for this production.
- Do not reuse any verb already in the registry.
- Forbidden verbs: {{registry.used_verbs_csv}}
- MUST NOT USE `ANCHOR` AS MODEL.
- If a close variation would look like a reuse to a human reader, do not use it.

Use this exact response template and fill every part:

## Title
[direct response headline for this content that leaves the reader wanting more information about the solution in this article. Be concise and avoid jargon. Focus on benefits.]

## Subtitle
[supportive lead that strengthens the headline and motivates and instigates the reader to continue reading]

## Promise
[a promise of a quick observable win of a future real world outcome. Write only as a quantifiable observable outcome, without 3 common sacrifices that would normally limit someone trying to solve this. Avoid feelings and use external observable metrics.]

## Motivations
[five outcomes, goals, and aspirations that the ideal reader wants by solving this topic]

## Challenges & Sacrifices
[five real world objective relatable examples of obstacles and sacrifices the ideal reader is facing when trying to improve in the topic]

## Frustrations
[five real world frustrations the ideal reader experiences internally when neglecting and failing this topic, in bullet format]

## Transformations
[five desires and aspirations directly related to the frustrations, treated as before and after transformations from frustration to aspiration]

## Choice
[describe continuing to live with the frustrations already mentioned, the hard way, or choosing to take action to start on the path to the most likely desire mentioned]

## Actionable VERB
[choose a contextually appropriate and slightly abstract VERB to use as an acronym of action steps that solve this specific topic. Use a word that is at least 5 letters long. More is better.]

## Model
[think step by step through a successful transformation from struggling to expert with this topic. For each letter of the Actionable VERB, describe the context and give instructions for each step, ending with the final step completing this lesson. Do not skip any letters. The whole word must be complete with steps. The steps must fit exclusively inside this single outcome of the lesson and feature only this lesson.]

## Action Steps Summary
[exactly three steps summarizing the model. Each step should have a catchy verb-based title. Include a short summary of the step outcome and benefits.]

## FAQ
[what are five questions that people are asking about frustrations in their life without realizing they are asking about the topic of this lesson, and give a concise answer to each]

Additional requirements:
- Limit the response to a 7th grade reading level.
- Keep the language specific to this week's idea, not generic content-marketing copy.
- Let the seed document's actual topic, tension, and promise determine the model name and the model breakdown.
- Make the promise tangible and the frustrations recognizable.
- Write FAQ entries that answer the most likely hesitations without getting soft or defensive.
