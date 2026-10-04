from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any


def openai_rendered_image_analyzer(api_key: str, *, model: str = "gpt-5-mini", timeout: int = 180):
    """Measure rendered thumbnail pixels. This adapter never decides PASS/FAIL."""
    key=str(api_key or "").strip()
    if not key:
        raise ValueError("OpenAI API key is required for rendered-image analysis.")

    def analyze(image_path: Path, expected: dict[str, Any]) -> dict[str, Any]:
        raw=Path(image_path).read_bytes()
        suffix=Path(image_path).suffix.casefold()
        mime="image/png" if suffix==".png" else "image/jpeg"
        data_url=f"data:{mime};base64,"+base64.b64encode(raw).decode("ascii")

        expected_bands=[{
            "band_id":x.get("band_id"),"text":x.get("text"),
            "x_pct":x.get("x_pct"),"y_pct":x.get("y_pct"),"w_pct":x.get("w_pct"),"h_pct":x.get("h_pct"),
        } for x in (expected.get("text_bands") or []) if x.get("text")]
        placements=[{
            "role_id":x.get("role_id"),"kind":x.get("kind"),
            "is_primary_target":bool(x.get("is_primary_target")),
            "description":x.get("description"),
        } for x in (expected.get("visual_placements") or [])]

        instruction="""Inspect ONLY the supplied rendered thumbnail pixels and return measurements, not a quality verdict.
The expected Phase-1 contract is supplied only to give canonical band text and visual role_ids. Do not claim an element is visible merely because it is expected.
Measure all visible text in reading order. For each visible text band return exact OCR text, approximate x/y/w/h as percentages of the full canvas, baseline rotation_deg, and glyph slant_deg. Keep physically separate panels as separate bands; do not merge them to satisfy the contract.
Count visible people, independent informational objects, and attention devices (arrows/circles/highlights). Text itself is not an informational object. Background atmosphere and structural furniture are not informational objects unless they are independently emphasized as topic information.
Map the visibly dominant current-topic target to one of the supplied Phase-1 role_ids only when pixels support that mapping; otherwise return null. Do the same for the target of visible attention devices. The role_ids are canonical vocabulary, not evidence.
Report any visible text not represented by the expected text and any extra independent informational objects. Determine whether the bottom-right timestamp-safe area is visually clear.
Do not output PASS/FAIL. Do not invent missing counts. Return one JSON object only.

EXPECTED TEXT BANDS:
"""+json.dumps(expected_bands,ensure_ascii=False)+"""

EXPECTED VISUAL PLACEMENTS / ROLE IDS:
"""+json.dumps(placements,ensure_ascii=False)

        schema={
            "type":"object",
            "properties":{
                "text_bands":{"type":"array","items":{"type":"object","properties":{
                    "text":{"type":"string"},"x_pct":{"type":"number"},"y_pct":{"type":"number"},
                    "w_pct":{"type":"number"},"h_pct":{"type":"number"},
                    "rotation_deg":{"type":"number"},"slant_deg":{"type":"number"}
                },"required":["text","x_pct","y_pct","w_pct","h_pct","rotation_deg","slant_deg"],"additionalProperties":False}},
                "people_count":{"type":"integer"},"informational_object_count":{"type":"integer"},
                "attention_device_count":{"type":"integer"},
                "primary_target_role_id":{"type":["string","null"]},
                "attention_target_role_id":{"type":["string","null"]},
                "extra_visible_text":{"type":"array","items":{"type":"string"}},
                "extra_informational_objects":{"type":"array","items":{"type":"string"}},
                "timestamp_safe_zone_clear":{"type":"boolean"}
            },
            "required":["text_bands","people_count","informational_object_count","attention_device_count","primary_target_role_id","attention_target_role_id","extra_visible_text","extra_informational_objects","timestamp_safe_zone_clear"],
            "additionalProperties":False
        }
        payload={
            "model":model,
            "input":[{"role":"user","content":[{"type":"input_text","text":instruction},{"type":"input_image","image_url":data_url}]}],
            "text":{"format":{"type":"json_schema","name":"rendered_thumbnail_observation","strict":True,"schema":schema}}
        }
        req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode("utf-8"),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"},method="POST")
        with urllib.request.urlopen(req,timeout=timeout) as response:
            body=json.loads(response.read().decode("utf-8"))
        output_text=str(body.get("output_text") or "").strip()
        if not output_text:
            for item in body.get("output") or []:
                for part in item.get("content") or []:
                    if part.get("type")=="output_text":
                        output_text=str(part.get("text") or "").strip()
                        if output_text: break
                if output_text: break
        observed=json.loads(output_text)
        if not isinstance(observed,dict):
            raise ValueError("Rendered-image analyzer must return one JSON object.")
        observed["source_image"]=str(image_path)
        observed["measurement_only"]=True
        return observed

    return analyze
