# V2 Read-Only Contract

The Thumbnail Pipeline may inspect existing V2 data but must not mutate it.

Current approved read source:
- `Analytics/youtube_assets/<asset_id>/thumbnails/*`

Observed V2 layout is treated as external input. No file is moved, renamed, deduplicated, cleaned, or rewritten.

Performance integration is intentionally adapter-based. The Thumbnail Pipeline accepts a read-only CSV/JSON/JSONL performance export and normalizes common fields:
`asset_id/project_id`, `video_id`, `title`, `ctr`, `impressions`, `views`, `watch_time`, `avd`, `upload_date`.

All derived data must be written under `Thumbnail_Pipeline/outputs/`.

Important: multiple historical thumbnail snapshots can exist for one asset. They remain separate observations until a reliable effective-date/performance-window mapping is available; the system must not pretend each snapshot caused the same CTR.
