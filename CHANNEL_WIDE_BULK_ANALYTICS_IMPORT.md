# Content / Performance Analytics Workflow

Traffic Source is removed from the active analytics workflow for now.

## Recurring update
Upload channel-wide YouTube Studio Content / Performance CSV exports.

The importer:
- accepts one or multiple Content/Performance CSV files
- matches by YouTube Video ID first
- falls back to exact normalized title
- creates YouTube-only records for new videos
- preserves project links, Actual Timeline snapshots, and transcript snapshots
- rejects Traffic Source reports so they cannot be attached incorrectly

## One-time/static data
Do not re-upload these every day:
- project identity
- Actual Timeline snapshot
- timestamped transcript fallback
- YouTube Video ID once linked

## Core improvement metrics
Views, Impressions, CTR, Watch Time, Average View Duration,
Average Percentage Viewed, and Subscribers.

Existing Traffic Source tables remain only for backward compatibility with old DBs.
The current UI and improvement workflow do not use them.
