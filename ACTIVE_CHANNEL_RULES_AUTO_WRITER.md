# Active Channel Script Rules — Automatic Writer Feedback Loop

The analytics system now converts repeated retention-linked script diagnoses into a
persistent rule lifecycle:

- OBSERVATION: 1 learning-eligible video
- EMERGING: 2 learning-eligible videos
- ACTIVE: 3+ learning-eligible videos
- RETIRED: previously known rule is no longer supported by current evidence

Only ACTIVE rules are automatically applied.

## Automatic injection

ACTIVE rules are written to:

`Analytics/active_channel_script_rules.md`

They are automatically consumed by:

1. Script Outline stage
2. Prepare Opus Package stage
3. Writer Workspace download (defensive injection if the generated package omitted them)

The rules are subordinate to:
- immutable user-supplied winning title
- approved research/evidence
- Medical Gate requirements
- necessary safety language

Retention learning may improve pacing, structure, clarity and payoff timing, but it
cannot override medical accuracy.

## No manual copy/paste

As new retention files are imported and the Analytics page is opened, the lifecycle
is synchronized automatically. A rule activates or retires based on current
cross-video evidence.
