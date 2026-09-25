# Thumbnail Intelligence Settings

The dashboard is the normal control surface for user-owned intelligence thresholds.

## Editable settings
- Minimum eligible impressions
- Full-reliability impressions

## Save behavior
- Load current values from `Thumbnail_Pipeline/config/intelligence.json`.
- Save only through the dashboard settings action.
- Validate integers: minimum >= 1 and full reliability >= minimum.
- Preserve all unrelated config keys.
- Write atomically (temporary file then replace).
- Record an append-only audit entry under `Thumbnail_Pipeline/outputs/settings/settings_audit.jsonl`.
- Analyzer/intelligence code must read these values from config and must not redefine them.

Direct manual JSON editing is not the intended workflow.
