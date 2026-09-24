from __future__ import annotations
from typing import Any

def verify_thumbnail(*,requested:dict[str,Any],observed:dict[str,Any])->dict[str,Any]:
    """Verify a rendered thumbnail against explicit requested constraints.

    This is a verification stage, not a prompt-rewrite or image-generation stage.
    Unknown/unmeasured requirements remain NEEDS_REVIEW rather than being guessed.
    """
    checks=[]
    def check(name:str, expected:Any, actual:Any, *, critical:bool=True):
        if actual is None:
            status="NEEDS_REVIEW"
        elif actual==expected:
            status="PASS"
        else:
            status="FAIL"
        checks.append({"requirement":name,"expected":expected,"observed":actual,"status":status,"critical":critical})

    for key in ("aspect_ratio","thumbnail_text","human_count","face_count","safe_zone_clear","presenter_position","text_zone","hero_count"):
        if key in requested:
            check(key,requested[key],observed.get(key),critical=True)

    # Explicit forbidden items are verified individually when detector/reviewer observations exist.
    for item in requested.get("forbidden_items",[]) or []:
        actual=(observed.get("forbidden_items_detected") or {}).get(item)
        if actual is None:
            checks.append({"requirement":f"forbidden:{item}","expected":False,"observed":None,"status":"NEEDS_REVIEW","critical":True})
        else:
            check(f"forbidden:{item}",False,bool(actual),critical=True)

    failed=[x for x in checks if x["status"]=="FAIL" and x["critical"]]
    review=[x for x in checks if x["status"]=="NEEDS_REVIEW" and x["critical"]]
    verdict="FAIL" if failed else ("NEEDS_REVIEW" if review else "PASS")
    return {
        "verdict":verdict,
        "checks":checks,
        "failed_requirements":[x["requirement"] for x in failed],
        "needs_review":[x["requirement"] for x in review],
        "policy":"verify_explicit_request_only",
        "notes":"Do not infer compliance for requirements that were not actually observed. The verifier reports whether the rendered thumbnail implemented the user's explicit instructions; it does not rewrite the prompt or generate another image.",
    }
