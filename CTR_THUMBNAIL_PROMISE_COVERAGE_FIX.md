# CTR Thumbnail Promise Coverage Fix

Narrow update to `Agents/Thumbnail_Agent.md` only.

Adds a Whole-Video Promise Coverage / Topic Representativeness gate so a technically complementary, visually unresolved concept cannot win by compressing a broad title into a narrow subsection.

Key behavior:
- Adds `Whole-Video Promise Coverage` to diagnosis.
- Adds `Promise Coverage: 0-10` to text-option/concept evaluation.
- Overall winner requires Promise Coverage >= 7/10.
- Cold-viewer scope test asks what the thumbnail makes the whole video appear to be about.
- List-title handling distinguishes a valid single-hero gateway from a misleading single-item tutorial/subtopic.
- Existing immutable-title, medical-safety, ACTIVE-rule, gap-quality, focal-load, and pointer-restraint behavior remains intact.
