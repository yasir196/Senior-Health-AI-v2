# CTR Thumbnail Auto-Sync Implementation

## Goal
Collapse the former manual six-stage thumbnail workflow into the existing **Sync YouTube Analytics** action.

## Behavior
After a successful YouTube analytics sync, the app now automatically:

1. Reads every permanent YouTube Video ID already in Analytics.
2. Downloads/checks the current published thumbnail directly from YouTube.
3. Compares SHA-256 against the latest stored snapshot; unchanged artwork is skipped without creating a duplicate snapshot or repeat vision cost.
4. Vision-analyzes only pending new/changed thumbnails, including exact visible thumbnail text and packaging features.
5. Joins eligible measured CTR + impressions evidence using the existing attribution rules.
6. Refreshes contextual packaging comparisons and Stage-5 candidate rules automatically.
7. Rewrites `Analytics/active_channel_packaging_rules.md` from the existing ACTIVE rule set.

No six-stage manual input is required.

## UI
The former `CTR / Thumbnails` stage controls are replaced by a single **Thumbnail Learning** view containing:
- current thumbnail/analyzed/CTR-joined/ACTIVE counts,
- extracted thumbnail text + packaging table,
- automatic channel-learning candidate review,
- optional manual Promote / Reject / Retire actions.

Promotion remains evidence-gated and deliberate. Candidate generation is automatic; ACTIVE status is not silently assigned.

## Preservation
- Existing SQLite data/schema is preserved.
- Existing thumbnail-version attribution logic is preserved.
- Senior Clarity rules are preserved.
- Channel thumbnail-text learning is preserved.
- Windows UTF-8 subprocess decoding fix is preserved.
- Unchanged thumbnails are not re-analyzed.
