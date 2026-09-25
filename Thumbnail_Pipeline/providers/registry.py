from __future__ import annotations
from typing import Any, Callable

BackendFactory = Callable[[dict[str, Any]], Any]

class ProviderRegistry:
    """Explicit provider registry. No vendor backend or secret is bundled."""
    def __init__(self) -> None:
        self._factories: dict[str, BackendFactory] = {}

    def register(self, name: str, factory: BackendFactory) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("Provider name is required.")
        if key in self._factories:
            raise ValueError(f"Provider already registered: {key}")
        self._factories[key] = factory

    def build(self, name: str, config: dict[str, Any] | None = None) -> Any:
        key = name.strip().lower()
        if key not in self._factories:
            raise ValueError(f"Unknown image provider: {key}")
        backend = self._factories[key](dict(config or {}))
        if backend is None or not callable(getattr(backend, "generate", None)):
            raise ValueError("Provider factory must return a backend with generate(request).")
        return backend

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

def validate_provider_config(config: dict[str, Any]) -> dict[str, Any]:
    provider = str(config.get("provider") or "").strip().lower()
    if not provider:
        raise ValueError("Image provider must be explicitly configured.")
    settings = config.get("settings") or {}
    if not isinstance(settings, dict):
        raise ValueError("Provider settings must be a mapping.")
    forbidden = {"api_key","token","secret","password","authorization"}
    leaked = forbidden.intersection(k.lower() for k in settings)
    if leaked:
        raise ValueError("Secrets must not be stored in Thumbnail_Pipeline provider config.")
    return {"schema_version":"0.15.0","provider":provider,"settings":dict(settings)}
