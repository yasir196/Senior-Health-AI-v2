# Duplicate Text Overlay Anchor Auto-Resolution

## Change
Text overlay validation now automatically resolves repeated script anchors instead of immediately failing with `script anchor mismatch`.

When an anchor phrase occurs more than once in `08_actual_timeline.csv`, the validator:
1. Finds all normalized exact occurrences.
2. Uses overlay narration order / the previously resolved overlay to select the intended chronological occurrence.
3. Builds and stores a unique surrounding-narration context for that occurrence.
4. Keeps timing on the original anchor phrase, so the context expansion does not widen overlay timing or create a new overlap.
5. Emits a warning noting that duplicate-anchor disambiguation was automatic and no manual edit was required.

Normal mismatch and overlap validation remain active.

## Regression tests
- Duplicate early occurrence auto-resolves without manual editing.
- Duplicate later occurrence resolves correctly when a preceding overlay places it later in narration.
- Existing text overlay tests continue to pass.
