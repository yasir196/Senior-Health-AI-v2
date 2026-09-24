# Thumbnail Intelligence Audit Dashboard

Purpose: make every learned conclusion inspectable by both a human and an AI agent.

The dashboard must never show a winner/loser conclusion without its evidence trail.

## Required views
1. Overview — eligible/excluded observations, category coverage, winner/loser counts, data warnings.
2. Winner Patterns — exact pattern, full thumbnail text, title, CTR, impressions, visual features, repeated observations.
3. Loser Patterns — same evidence plus separate Suggestion for Loser.
4. Title + Thumbnail Pair — immutable title beside full OCR thumbnail text, overlap/complement and hook/psychology pattern.
5. Text Pattern Audit — full text, every OCR word/phrase, assigned tag(s), unmatched words, overall pattern.
6. Image Audit — source thumbnail beside detected face boxes/composition/saliency/readability metrics when available.
7. Mistake Review — human can flag OCR error, wrong pattern, wrong category, wrong title pairing, wrong performance match, or other issue.
8. AI Handoff — machine-readable audit payload containing the same evidence and human flags.

## Display rules
- Never abbreviate thumbnail text in evidence views.
- Always show title and thumbnail text together.
- Always show CTR with impressions.
- Always distinguish OBSERVED, INFERRED, and HUMAN-CORRECTED values.
- Never hide UNCLASSIFIED words.
- Never silently overwrite analyzer output after a human correction.
- Human correction is an overlay with original value preserved.
