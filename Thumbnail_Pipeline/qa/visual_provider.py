from __future__ import annotations
from typing import Any, Protocol

_VISUAL_KEYS = ("layout_matches","subject_placement_matches","text_placement_matches","safe_zone_clear")

class VisualQAProvider(Protocol):
    def inspect(self, request: dict[str, Any]) -> dict[str, Any]: ...

def build_visual_qa_request(artifact: dict[str, Any]) -> dict[str, Any]:
    asset = artifact.get("asset") or {}
    contract = artifact.get("render_contract") or {}
    if not asset.get("output_path"):
        raise ValueError("Visual QA requires a rendered output_path.")
    required=("layout","subject_placement","text_placement","safe_zone")
    missing=[k for k in required if contract.get(k) in (None,"")]
    if missing:
        raise ValueError(f"Visual QA contract is unresolved: {missing}")
    return {"schema_version":"0.16.0","immutable_title":artifact.get("immutable_title") or "","asset":{"output_path":asset["output_path"],"width":asset.get("width"),"height":asset.get("height")},"expected":{"layout":contract["layout"],"subject_placement":contract["subject_placement"],"text_placement":contract["text_placement"],"safe_zone":contract["safe_zone"]}}

def inspect_visual_qa(artifact: dict[str, Any], provider: VisualQAProvider) -> dict[str, Any]:
    if provider is None:
        raise ValueError("Visual QA provider is required.")
    raw=provider.inspect(build_visual_qa_request(artifact))
    if not isinstance(raw,dict):
        raise ValueError("Visual QA provider result must be a mapping.")
    observed={}
    for key in _VISUAL_KEYS:
        value=raw.get(key)
        observed[key]=value if isinstance(value,bool) else None
    return {"schema_version":"0.16.0","observed":observed,"provider_evidence":raw.get("evidence"),"complete":all(isinstance(observed[k],bool) for k in _VISUAL_KEYS)}
