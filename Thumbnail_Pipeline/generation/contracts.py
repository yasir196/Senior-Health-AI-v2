from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any

@dataclass
class GenerationRequest:
    audit_id:int
    title:str
    proposed_thumbnail_text:str
    prompt:str
    source_thumbnail_path:str
    aspect_ratio:str="16:9"
    provider:str="configured_image_provider"
    def payload(self)->dict[str,Any]: return asdict(self)

REQUIRED_CONTRACT="""EDIT the supplied source thumbnail into one new 16:9 YouTube thumbnail candidate.
The source thumbnail is mandatory and is the image-edit target, not loose inspiration.
Follow the visible human-editable prompt exactly. Preserve the supplied video title as context only; do not rewrite it.
Render only the explicitly proposed thumbnail text. Preserve composition/safe-zone and senior-health constraints supplied by the prompt.
Do not silently rewrite the human-edited prompt before generation.""".strip()

def final_generation_prompt(request:GenerationRequest)->str:
    if not request.source_thumbnail_path.strip(): raise ValueError("source_thumbnail_path is required for loser thumbnail editing")
    return f"{REQUIRED_CONTRACT}\n\nSOURCE THUMBNAIL TO EDIT:\n{request.source_thumbnail_path}\n\nVIDEO TITLE (context only):\n{request.title}\n\nTHUMBNAIL TEXT:\n{request.proposed_thumbnail_text}\n\nHUMAN-EDITABLE EDIT PROMPT:\n{request.prompt}".strip()
