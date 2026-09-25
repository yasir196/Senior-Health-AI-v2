# V2 Read-Only Contract

Thumbnail Pipeline may read existing V2 evidence but must not mutate V2.

Approved read sources include:
- `Analytics/youtube_assets/<asset_id>/thumbnails/*`;
- the existing V2 analytics SQLite database through URI `mode=ro` + `PRAGMA query_only=ON`;
- existing V2 YouTube OAuth client/token files through the read-only adapter.

OAuth refresh for Thumbnail Pipeline is performed in memory. It must not call V2's persistence path that rewrites the token file.

Existing V2 thumbnail/CTR attribution evidence is preferred over assigning lifetime CTR to arbitrary historical snapshots. All derived outputs stay under `Thumbnail_Pipeline/outputs/`. Dashboard-owned Thumbnail Pipeline settings may update only `Thumbnail_Pipeline/config/intelligence.json`.
