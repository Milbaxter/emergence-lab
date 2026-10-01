# Work worth reading

The team should produce fewer, stronger outputs. A result earns attention by helping a specific reader understand something or make a decision. A beautiful page cannot rescue an irrelevant question or an unsupported claim.

## Before the experiment

The scout supplies four parts of a reader brief:

- **Audience:** who is expected to use the result?
- **Decision:** what could they do differently after reading it?
- **Need:** what observed problem justifies the work? If demand is assumed, say so.
- **Difference:** what does this add beyond existing knowledge or previous missions?

The critic checks that brief, the baseline, and the proposed measurement before code runs. A tautology, duplicate exercise, or arbitrary benchmark should be reframed or stopped. A small negative result can be useful when it prevents a plausible bad decision. Complexity and novelty are not requirements.

## From finding to finished note

The editor works from an evidence-checked finding and its execution receipts. The note is at most 650 words, using these fields: title, takeaway, audience, why it matters, what was tested, result, what to do, limitations, and next step. Write the conclusion early; define unfamiliar terms; put scope beside any recommendation. Quantitative claims need the baseline, comparison, and important failure cases. Readers should not need the agent transcript to understand the result.

The page uses a restrained, readable layout, with the takeaway and action prominent and the process below. It exports as self-contained HTML suitable for sharing or printing. Evidence references and edition hashes provide traceability; they do not constitute independent replication. Downloaded copies are snapshots and cannot be recalled if a claim is later withdrawn.

A separate reader reviews the exact draft in a fresh invocation, without prior conversation or the writer's self-assessment:

| Check | The question |
|---|---|
| Usefulness | Does this help the stated reader make the stated decision? |
| Evidence | Do the comparisons and conclusions follow from the recorded runs, including failures? |
| Clarity | Can the reader explain the takeaway without decoding internal jargon? |
| Actionability | Is the suggested next step specific, proportionate, and justified? |
| Restraint | Are scope, uncertainty, and negative results represented without hype? |

Each check names a report field, quotes an exact passage, and explains the assessment. The evidence check identifies a supporting run. The harness validates those references and rejects missing or repeated boilerplate explanations. It cannot mechanically determine whether a well-formed explanation is substantively correct. The reader should identify a concrete defect and a useful correction when failing a check.

One rewrite and a fresh review are allowed. An unchanged rewrite is blocked. Unresolved defects, insufficient evidence, and exhausted allowance leave the work withheld or unfinished. Drafts remain available for inspection and later learning. The agents do not need the owner's approval to make any of these decisions.

## Learning whether people care

The owner can mark a note useful or not useful and explain why. The latest four feedback records on still-ready, still-checked findings are supplied to later missions in the same demo/live partition. Feedback can be changed; agents never wait for it. There is no automatic relevance score, reward optimization, or claim that one owner's preferences represent a wider audience.

For a future human evaluation, sample completed and withheld work, hide which process generated it, and ask readers whether they can explain the result, identify its limits, and name an action it changes. Compare with a single-agent baseline at matched resources. Track specific defects corrected and total cost per useful result. Do not reward word count, consensus, number of reports, or the fraction that agents approve.
