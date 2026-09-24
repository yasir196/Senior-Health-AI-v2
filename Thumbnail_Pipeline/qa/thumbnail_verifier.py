from __future__ import annotations
from typing import Any

def verify_thumbnail(*, audit_edit_contract:dict[str,Any], observed:dict[str,Any])->dict[str,Any]:
    """Verify the edited thumbnail against the AI audit/loser-repair contract.

    The governing intent is the audit-generated edit recommendation/prompt, not a
    separately invented verifier policy and not a new user-authored requirement.
    """
    requested=audit_edit_contract
    checks=[]
    def check(name:str,expected:Any,actual:Any,critical:bool=True):
        status="NEEDS_REVIEW" if actual is None else ("PASS" if actual==expected else "FAIL")
        checks.append({"requirement":name,"expected":expected,"observed":actual,"status":status,"critical":critical})

    # Structured requirements extracted/stored with the AI loser edit recommendation.
    for key in ("aspect_ratio","proposed_thumbnail_text","human_count","face_count","safe_zone_clear","presenter_position","text_zone","hero_count"):
        if key in requested:
            observed_key="thumbnail_text" if key=="proposed_thumbnail_text" else key
            check(key,requested[key],observed.get(observed_key))

    for item in requested.get("forbidden_items",[]) or []:
        actual=(observed.get("forbidden_items_detected") or {}).get(item)
        if actual is None:
            checks.append({"requirement":f"forbidden:{item}","expected":False,"observed":None,"status":"NEEDS_REVIEW","critical":True})
        else:
            check(f"forbidden:{item}",False,bool(actual))

    # Audit repair points can be supplied as machine-verifiable structured checks.
    for repair in requested.get("repair_checks",[]) or []:
        name=repair["name"]; expected=repair.get("expected")
        check(f"repair:{name}",expected,(observed.get("repair_checks") or {}).get(name),bool(repair.get("critical",True)))

    failed=[x for x in checks if x["critical"] and x["status"]=="FAIL"]
    review=[x for x in checks if x["critical"] and x["status"]=="NEEDS_REVIEW"]
    verdict="FAIL" if failed else ("NEEDS_REVIEW" if review else "PASS")
    return {
        "verdict":verdict,
        "verification_source":"ai_audit_loser_edit_contract",
        "audit_id":requested.get("audit_id"),
        "checks":checks,
        "failed_requirements":[x["requirement"] for x in failed],
        "needs_review":[x["requirement"] for x in review],
        "notes":"Checks whether the edited thumbnail implemented the AI audit's loser-repair recommendation/edit prompt. It does not invent new requirements or regenerate the image.",
    }
