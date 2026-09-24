from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class GenerationRequest:
    audit_id: int
    title: str
    proposed_thumbnail_text: str
    prompt: str
    aspect_ratio: str = "16:9"
    provider: str = "configured_image_provider"

    def payload(self) -> dict[str, Any]:
        return asdict(self)

REQUIRED_CONTRACT = """
Generate a 16:9 YouTube thumbnail candidate. Follow the supplied prompt exactly.
Preserve the supplied video title as context; do not rewrite the title.
Render only the explicitly proposed thumbnail text.
Keep the result suitable for senior-health educational content and preserve any composition/safe-zone constraints in the prompt.
""".strip()

def final_generation_prompt(request: GenerationRequest) -> str:
    return f"{REQUIRED_CONTRACT}\n\nVIDEO TITLE (context only):\n{request.title}\n\nTHUMBNAIL TEXT:\n{request.proposed_thumbnail_text}\n\nEDITABLE PROMPT:\n{request.prompt}".strip()
