# Thumbnail Pipeline — Phase 1

Isolated thumbnail intelligence subsystem for Senior Health AI V2.

## Hard boundary
- Existing V2 files are inputs only and are treated as read-only.
- This subsystem writes only inside `Thumbnail_Pipeline/`.
- No existing V2 agent, system file, config, analytics file, project file, or production flow is modified.
- Any future write-back/integration with V2 requires an explicit approved contract.

## Phase 1
Historical Analyzer foundation:
1. discover/read thumbnail inputs supplied to this subsystem;
2. extract deterministic visual features;
3. write analysis artifacts under `Thumbnail_Pipeline/outputs/`;
4. later join those features to existing V2 analytics through a read-only adapter.

No thumbnail generator is included in Phase 1.
