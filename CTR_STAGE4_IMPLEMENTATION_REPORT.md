# CTR Thumbnail Packaging Learning — Stage 4

Implemented contextual, impression-aware cross-video packaging comparisons on top of Stage 3 evidence.

## Behavior
- Uses exactly one latest Stage-3 evidence row per analytics_id to avoid duplicate weighting after re-analysis.
- Builds channel-wide comparisons and hero-category contextual comparisons when at least two videos exist in that context.
- Uses impression-weighted CTR for feature-vs-other-observed-value comparisons.
- Stores immutable comparison runs plus structured associations in SQLite.
- Maturity: 1 video = OBSERVATION; 2 = REPEATED SIGNAL; 3+ = CHANNEL PATTERN CANDIDATE.
- Explicitly labels results as correlational associations, never causal rules.
- Does not create or activate packaging rules; rule promotion remains Stage 5.
- Preserves historical-thumbnail attribution caveats inherited from Stage 3.

## Schema
Schema version 7 adds:
- thumbnail_packaging_comparison_runs
- thumbnail_packaging_associations

Existing database rows are preserved by CREATE IF NOT EXISTS migration.

## Validation
- Stage 4 targeted + Stage 3 tests: 10 passed.
- Stage 1→4 + linking/provenance/retention regression: 29 passed.
- Python compile: PASS.
- Broad suite excluding two stale-path collection tests: 473 passed, 15 pre-existing/unrelated failures.
