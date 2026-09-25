from __future__ import annotations
from typing import Protocol
from .contracts import GenerationRequest

class ImageGenerationProvider(Protocol):
    def generate(self, request: GenerationRequest) -> dict:
        ...

class NotConfiguredProvider:
    def generate(self, request: GenerationRequest) -> dict:
        raise RuntimeError(
            "Image generation provider is not configured. Dashboard must not fake a generated image."
        )
