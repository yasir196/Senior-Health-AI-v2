# CTR Historical Pattern Examples Fix

## Scope
Narrow fix to make ACTIVE thumbnail packaging rules expose and use the real historical channel thumbnail patterns that produced the learned signal.

## Changes
- Historical exemplar query now includes the exact extracted `thumbnail_text` and text style.
- Exemplar retrieval preserves historical thumbnail versions instead of looking only at the current/latest version.
- ACTIVE rule exemplars prioritize the original Stage-4 source cohort using the association's stored `analytics_ids`.
- Matching examples include measured CTR, impressions, text structure, layout/presenter/hero/color/contrast traits, and archived thumbnail file path when available.
- `active_channel_packaging_rules.md` newline rendering was repaired so examples are readable as real Markdown.
- Immediately before every Thumbnail Agent run, the ACTIVE packaging artifact is re-rendered from the current analytics DB. This removes the stale-artifact problem when a rule was promoted after the last YouTube sync.
- If analytics refresh fails temporarily, the last valid ACTIVE artifact is preserved and the Thumbnail run is not blocked.

## Unchanged
- No title generation/repair logic changed.
- No CTR thresholds, promotion gates, ACTIVE/CANDIDATE decisions, medical rules, script learning, or unrelated workflow behavior changed.
- Historical examples remain pattern references only; wording must not be copied verbatim and associations are not treated as causal guarantees.

## Verification
- Thumbnail test suite: 51/51 PASS.
- Python compile: PASS.
- ZIP integrity: PASS before delivery.
