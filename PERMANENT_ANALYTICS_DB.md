# Permanent Analytics DB

The `Analytics/senior_health_analytics.db` database is independent of `Projects/`.

## Lifecycle
- Project creation -> permanent analytics record is created automatically.
- Actual Timeline generation -> `08_actual_timeline.csv` + lightweight Production Sheet fields are snapshotted permanently.
- Project folder can later be deleted -> analytics record remains; folder status becomes `deleted`.
- Existing YouTube videos with no local project -> register using exact title; Video ID is optional.
- No Actual Timeline -> upload timestamped transcript in `[HH:MM:SS] text` format.
- Transcript reconstruction is stored as `TS0001...` with source `transcript_reconstructed`, never mislabeled as original `S###` scenes.

## YouTube Studio imports
Supported CSV shapes:
- Performance / Content summary
- Traffic Source summary
- Daily Totals
- Date x Traffic Source chart data

Missing values are stored as SQL NULL, not zero.

## Permanent identity
`analytics_id` is the database identity.
A YouTube Video ID can be added later and becomes the stable published-video identity when available.
