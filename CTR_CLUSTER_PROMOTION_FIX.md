# CTR Correlated Signal Cluster Promotion Fix

- Adds direct manual promotion of a consolidated signal cluster as ONE ACTIVE packaging rule.
- Representative signal must independently pass the existing Stage-5 promotion audit.
- Supporting correlated rows are stored as evidence only; CTR deltas are never summed.
- Cluster construction is now context-specific (`context_type` + `context_value`) so channel-wide and hero-category evidence are not mixed.
- ACTIVE cluster guidance is written to `Analytics/active_channel_packaging_rules.md` and Thumbnail_Agent is instructed to treat it as one pattern, not a checklist of independent wins.
- Existing raw-rule review/promotion remains available.
