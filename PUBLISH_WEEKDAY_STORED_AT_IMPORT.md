# Publish Weekday Stored at Import

When a Content/Performance CSV is imported:

1. `Video publish time` is normalized to ISO `publish_date`.
2. Weekday is calculated immediately from that date.
3. Both values are saved permanently in `videos`:
   - `publish_date`
   - `publish_weekday`

Example:
`Aug 5, 2026` -> `2026-08-05` + `Wednesday`

Existing databases are migrated automatically with the new `publish_weekday` column.
Legacy rows without a stored weekday can still be backfilled from `publish_date` in reports.
