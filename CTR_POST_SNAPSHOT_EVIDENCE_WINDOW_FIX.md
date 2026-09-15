# CTR Post-Snapshot Evidence Window Fix

Implemented on top of the Stage 6 Promotion Audit Fix build.

## Behavior
- Stage 3 now prefers daily Reach rows strictly AFTER the archived thumbnail snapshot calendar date.
- Same-day Reach rows are excluded from the clean window to avoid pre-snapshot impressions contaminating attribution.
- Clean evidence uses metric_source `reach_daily_post_snapshot` and attribution_status `post_snapshot_window_observed`.
- If no post-snapshot daily Reach rows exist, the prior historical evidence fallback remains and stays `historical_thumbnail_version_uncertain`.
- Stage 4 attribution now considers both the feature cohort and comparison cohort. Mixed historical/clean cohorts become `mixed_attribution_caveats`.
- Stage 5 promotion explicitly allows only `post_snapshot_window_observed` associations, while still requiring at least 3 videos in both feature and comparison groups.
- Stage 6 continues to consume only manually promoted ACTIVE rules.

## Interpretation
`post_snapshot_window_observed` is a temporal observational match, not causal proof. An unrecorded thumbnail change between snapshots cannot be ruled out.
