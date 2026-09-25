# Thumbnail Pipeline

Isolated thumbnail intelligence subsystem inside Senior Health AI V2.

## Hard boundary
Existing V2 code, config, analytics, OAuth files and project files are read-only inputs. Derived writes stay under `Thumbnail_Pipeline/`; analysis/audit artifacts stay under `Thumbnail_Pipeline/outputs/`.

## Connected stages
1. Read V2 attribution-aware thumbnail + CTR evidence.
2. Apply config-owned eligibility/reliability rules.
3. Compare within V2 categories and split eligible winner/loser evidence.
4. Discover thumbnail-text patterns from channel data without seeded psychology labels.
5. Build winner-only new-project prior; fall back to strongest eligible winner category when requested category has no winner.
6. Reuse V2 YouTube OAuth credentials read-only for same-topic, then same-category cross-channel references.
7. Inspect external title + thumbnail references together and preserve comparative view evidence without arbitrary outlier labels.
8. Keep losers in a separate repair lane and produce an editable image-edit prompt.
9. Verify a rendered repair candidate against the structured AI audit edit contract.

The supplied project title remains immutable. External references broaden ideas; they do not override eligible channel winner evidence or import loser patterns as positive priors.
