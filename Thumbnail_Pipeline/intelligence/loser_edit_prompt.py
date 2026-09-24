from __future__ import annotations
from typing import Any


def build_loser_edit_prompt(
    *,
    title: str,
    original_text: str,
    proposed_text: str,
    loser_reasons: list[dict[str, Any]],
    winner_evidence: list[dict[str, Any]],
    original_visual: dict[str, Any] | None = None,
    target_visual: dict[str, Any] | None = None,
) -> str:
    """Build a complete image-edit prompt grounded in loser diagnosis + winner evidence."""
    original_visual = original_visual or {}
    target_visual = target_visual or {}

    reasons = "\n".join(
        f"- {x.get('feature','pattern')}: loser={x.get('higher_ctr_median', x.get('value','n/a'))}; evidence={x.get('interpretation', x.get('reason','observed lower-CTR association'))}"
        for x in loser_reasons
    ) or "- No reliable loser-specific reason available; do not invent one."

    winners = "\n".join(
        f"- Title: {x.get('title','n/a')} | Thumbnail text: {x.get('thumbnail_text','n/a')} | Pattern: {x.get('pattern','n/a')} | CTR: {x.get('ctr','n/a')} | Impressions: {x.get('impressions','n/a')}"
        for x in winner_evidence
    ) or "- No adequately sampled winner reference available; preserve conservative channel defaults."

    return f"""TASK: EDIT THE EXISTING LOSER THUMBNAIL INTO A NEW TEST CANDIDATE.

VIDEO TITLE — IMMUTABLE:
{title}

ORIGINAL THUMBNAIL TEXT — FULL:
{original_text}

REPLACEMENT THUMBNAIL TEXT — EXACT:
{proposed_text}

WHY THE ORIGINAL IS BEING REWORKED:
{reasons}

SAME-CATEGORY WINNER EVIDENCE USED FOR THIS EDIT:
{winners}

ORIGINAL VISUAL OBSERVATIONS:
{original_visual}

TARGET VISUAL DIRECTION:
{target_visual}

EDIT INSTRUCTIONS:
- Treat the supplied original thumbnail as the image to edit, not as loose inspiration.
- Preserve useful identity/subject elements unless TARGET VISUAL DIRECTION explicitly asks to change them.
- Correct the diagnosed loser characteristics only where supported by the evidence above.
- Use the REPLACEMENT THUMBNAIL TEXT exactly. Do not paraphrase, add, remove, merge, or misspell words.
- Make the full thumbnail text clearly readable at mobile size.
- Preserve strong separation between text and subject; avoid collisions, merged letters, and visual clutter.
- Keep one dominant visual idea. Do not add unrelated objects or extra scenes.
- Respect the channel's 16:9 composition and timestamp-safe area when specified by the target direction.
- For senior-health content, keep the scene educational rather than clinical; do not introduce doctor/scrubs/badge cues unless explicitly required.
- Do not add unsupported medical claims, diagnosis cues, cure/reversal claims, pills, anatomy, arrows, badges, or extra labels unless explicitly requested.
- Do not change the video title; it is context only and must not be rendered into the image unless it is identical to the replacement thumbnail text.
- Output one fresh edited thumbnail candidate, 16:9.

AUDIT REQUIREMENT:
The generated candidate must remain traceable to this exact prompt. Do not silently rewrite these instructions before generation.
""".strip()
