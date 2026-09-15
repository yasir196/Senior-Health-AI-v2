# Claude Opus Master Writer Prompt

Write the final production-ready narration for the selected project using the existing outline, research, approved claims, host identity, templates, runtime target, retention structure, visual cues, cautions, and CTA rules.

Do not research again, add sources, add or strengthen medical claims, invent credentials, or imply the virtual host is a licensed clinician.

## Required Separate Outputs

Create exactly these separate files:

1. `06_final_script.md` — narration only, with title, section headings, spoken narration, `[Visual Cue: ...]` blocks, cautions, and CTA. Do not include QA reports, scorecards, runtime tables, configuration notes, or process commentary.
2. `06_runtime_report.md` — word count, estimated narration runtime, target comparison, section runtimes, and assumed WPM.
3. `06_retention_report.md` — hook, open loops, pattern interrupts, section teasers, payoff, CTA placement, and retention risks.
4. `06_medical_review.md` — claims-preserved check, safety language, cautions, and unsupported-claim check. This is an editorial review, not a replacement for Medical Gate 2.
5. `06_humanization_report.md` — conversational score, host-voice score, emotional connection, repeated phrasing, contractions, rhetorical questions, and largest humanization changes.

Only narration may remain in `06_final_script.md`.

Use natural educator-to-viewer language, clear transitions, occasional rhetorical questions, concise paragraphs, and clearly illustrative stories. Preserve all approved medical meaning and safety caveats.


## Semantic Progression Lock

Before finalizing `06_final_script.md`, audit the narration beat by beat. Every major beat must materially ADVANCE the answer, DEEPEN it with a new distinction/evidence/mechanism/consequence, or deliver a necessary safety boundary. Do not treat paraphrasing as advancement. Do not repeat the same route, takeaway, warning, analogy, or personal-plan caveat merely for clarity or runtime. For any core idea that would appear 3+ times, apply a material-delta test before writing each later occurrence: be able to name the exact new viewer knowledge, decision, mechanism, consequence, evidence, or action it adds beyond the primary explanation. A different example/food/section, new wording, another hypothetical, or the same safety/scope reminder attached to a new stage is not enough. If no concrete delta exists, omit or merge it. Keep at most one concise final recap when it compresses rather than reteaches.

Recaps, stories, curiosity loops, and pattern interrupts are adaptive tools, not scheduled quotas. Do not insert them on a fixed minute cadence. Use at most the recap(s) genuinely needed for orientation and closure; never create multiple ending cycles such as recap → practical recap → "one final time" → final picture → conclusion recap of the same idea.

Pay off the core title question progressively from the opening onward. Do not postpone the substantive answer behind long setup or qualification, and avoid late phrases such as "now we can finally answer" when the title answer should already be underway.

Consolidate repeated safety/context boundaries while preserving every medically required warning and its meaning. If removing semantic repetition makes the script shorter than the configured runtime floor, add only evidence-approved NEW viewer value; never restore repetition or pad with another recap, disclaimer, analogy, or hypothetical story.

## Retention-First Drafting Lock

Write the first draft so the downstream Retention Structure Analyzer should need as few structural patches as possible, while leaving that analyzer fully independent. Apply only writing-relevant prevention rules here; do not imitate its scoring/report format or claim that the script has passed retention review.

- Deliver concrete promised value early. Do not bury the title payoff behind avoidable preamble, generic setup, repeated qualification, or a long safety block. Preserve any warning that genuinely must precede the action or claim.
- Keep hook promises and later payoffs continuous. If the opening promises a specific answer, example, comparison, mistake, number, or reveal, make sure the later script clearly delivers that exact promise without changing approved factual or medical substance.
- Treat pacing adaptively, not by timer. Do not manufacture re-hooks, stories, pattern interrupts, recaps, or curiosity lines on a fixed cadence. Use them only when they advance the viewer's understanding or bridge a real structural need.
- Prevent dense information delivery. Give each paragraph/beat a clear dominant idea and hierarchy; when several distinctions are necessary, sequence them so the viewer does not have to hold multiple new ideas at once.
- Prevent list fatigue and monotony. Within lists or repeated item structures, move efficiently from setup to useful value and vary the function of supporting explanation only when it adds genuine new information.
- Keep required care/safety guidance intact but concise, locally relevant, and non-repetitive. Do not scatter the same caution meaning across multiple sections when it can be stated once without changing medical meaning. Safety and medical accuracy always outrank retention guidance.
- Do not use qualification as a recurring interruption. After a necessary boundary is established, repeat it only when the later occurrence changes the viewer's action/decision at that exact point or otherwise passes the material-delta test.
- Keep transitions functional. A bridge should move the viewer to the next idea or payoff; do not add transition language that merely restates the section just completed.
- Keep the ending efficient. Deliver the final practical value, allow at most one concise compressive recap when genuinely useful, then place a brief CTA. Do not create recap → practical recap → second conclusion → CTA cycles.
- Runtime never protects weak structure. Do not retain repetition, delayed payoff, redundant caution, filler examples, extra hypotheticals, or recap material merely to satisfy the configured duration. If meaningful evidence-approved NEW value is unavailable, do not manufacture it.
- Apply every currently supplied ACTIVE CHANNEL SCRIPT RULE during drafting when it is contextually applicable. Do not hardcode historical rule names, counts, retention deltas, or thresholds into the script; use the current rules supplied in the project package. If an ACTIVE rule conflicts with approved evidence, medical accuracy, required safety language, or the immutable title, preserve the protected substance.

Before finalizing, do one silent retention-prevention pass over the draft: check early payoff, hook/payoff continuity, information density, list fatigue/monotony, safety/qualification momentum, semantic repetition/material delta, transitions, recap/ending cycles, and CTA placement. Revise only defects you can fix without changing approved facts, evidence, numbers, medical claims, required safety meaning, or the immutable title. The downstream Retention Structure Analyzer and Narrative QA remain the independent verification gates.

## Execution / No-Negotiation Lock

Do not pre-negotiate the assignment. Do not tell the user that the approved research is insufficient, estimate in advance how many words the evidence can support, propose a shorter target, discuss whether the minimum runtime is achievable, or stop to explain a word-count conflict before drafting. First write the strongest complete production-ready script using all approved material at legitimate depth and following the Semantic Progression Lock.

Target runtime/word count is a soft planning preference. The configured minimum and maximum are validation boundaries, not reasons to negotiate before writing. Do not stop drafting merely because the planned target or midpoint may not be reached. Do not ask for more research merely to reach a runtime target.

Only after `06_final_script.md` is complete, calculate the actual spoken word count and runtime in `06_runtime_report.md`. If the completed script falls below the configured minimum despite using all approved material without padding, report that fact in `06_runtime_report.md`; do not withhold, shorten, pad, or refuse to produce `06_final_script.md`. Never substitute filler, repeated cautions, extra hypotheticals, invented mechanisms, unsupported claims, or redundant recaps to chase duration.

