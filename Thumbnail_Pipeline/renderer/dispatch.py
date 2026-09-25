from __future__ import annotations

from typing import Any, Protocol


class RendererProvider(Protocol):
    def render(self, handoff: dict[str, Any]) -> dict[str, Any]:
        ...


def dispatch_renderer(
    handoff: dict[str, Any],
    *,
    provider: RendererProvider | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    """Explicit renderer boundary. Default is dry-run and performs no external action."""
    if handoff.get("renderer_status") != "not_invoked":
        raise ValueError("Invalid renderer handoff state.")
    if not execute:
        return {
            "schema_version": "0.5.0",
            "status": "dry_run",
            "renderer_invoked": False,
            "handoff": handoff,
        }
    if provider is None:
        raise ValueError("Renderer provider is required when execute=True.")

    result = provider.render(handoff)
    return {
        "schema_version": "0.5.0",
        "status": "rendered",
        "renderer_invoked": True,
        "result": result,
    }
