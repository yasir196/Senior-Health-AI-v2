# Cross-Video Script Pattern Learning

The Learning Engine now aggregates retention-linked script diagnoses across videos.

## Confidence
- WATCH: issue appears in 1 learning-eligible video
- REPEATED SIGNAL: issue appears in 2 learning-eligible videos
- CHANNEL PATTERN: issue appears in 3+ learning-eligible videos

A video is learning-eligible when its latest Content/Performance snapshot has:
- at least 30 views, OR
- at least 300 thumbnail impressions

This prevents tiny early samples from becoming channel writing rules.

## Output
For each repeated script issue:
- number of unique videos
- number of retention events
- average and median retention drop
- number of opening videos affected
- confidence level
- the most common future script rule

The evidence expander preserves the exact video, time window, event, issue,
retention change, and script/transcript excerpt behind every pattern.

The engine is advisory only. It does not automatically rewrite scripts or change
Medical Gates, titles, project files, or production assets.
