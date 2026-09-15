# CTR Thumbnail Text Intelligence Fix

This build extends the existing Stage 2→6 thumbnail CTR learning pipeline without changing the immutable-title flow or auto-activating rules.

## Added
- Deterministic `text_length_bucket` learning from existing Stage-2 visible thumbnail word counts: `0`, `1-3`, `4-5`, `6-7`, `8-10`, `11+` words.
- Deterministic `text_density_bucket` learning from existing word/line counts: `<=2`, `>2-4`, `>4` words per line.
- Both features now participate in Stage-4 channel-wide and hero-category CTR/impression comparisons.
- Existing Stage-5 fair-comparison / promotion audit remains unchanged: text rules stay CANDIDATE until explicitly promoted and must pass the same cohort/impression/attribution/CI gate.
- ACTIVE text-copy rules are injected through the existing `Analytics/active_channel_packaging_rules.md` boundary.
- Thumbnail Agent now explicitly consumes ACTIVE text-copy evidence while retaining Senior Comprehension and medical/title constraints.

## Important
- No 3-word, 8-10-word, or other winning length is hardcoded.
- Existing analyzed thumbnails do not require another vision/API analysis for length/density learning; the new buckets are derived from already stored exact word and line counts.
- Historical wording is never copied automatically; only the measured packaging structure can guide new project-specific text.
