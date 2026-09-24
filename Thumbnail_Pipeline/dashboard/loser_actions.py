from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.generation.contracts import GenerationRequest,final_generation_prompt
from Thumbnail_Pipeline.intelligence.loser_edit_prompt import build_loser_edit_prompt

def loser_repair_card(*,audit_id:int,title:str,original_text:str,source_thumbnail_path:str,why:list[dict[str,Any]],suggestion:dict[str,Any],proposed_text:str,original_visual:dict[str,Any]|None=None,target_visual:dict[str,Any]|None=None,human_prompt_override:str|None=None)->dict[str,Any]:
    winner_evidence=(suggestion.get("same_category_winner_evidence") or suggestion.get("suggestion_for_loser",{}).get("same_category_winner_evidence") or [])
    auto_prompt=build_loser_edit_prompt(title=title,original_text=original_text,proposed_text=proposed_text,loser_reasons=why,winner_evidence=winner_evidence,original_visual=original_visual,target_visual=target_visual)
    effective_prompt=human_prompt_override if human_prompt_override is not None else auto_prompt
    request=GenerationRequest(audit_id=audit_id,title=title,proposed_thumbnail_text=proposed_text,prompt=effective_prompt,source_thumbnail_path=source_thumbnail_path)
    return {"audit_id":audit_id,"title":title,"source_thumbnail_path":source_thumbnail_path,"original_thumbnail_text_full":original_text,"why_lower_ctr":why,"suggestion_for_loser":suggestion,"proposed_thumbnail_text":proposed_text,"generated_edit_prompt_original":auto_prompt,"editable_image_prompt":effective_prompt,"prompt_human_edited":human_prompt_override is not None,"generate_now":{"enabled":bool(source_thumbnail_path.strip()),"button_label":"Generate Now","request_preview":request.payload(),"final_prompt_preview":final_generation_prompt(request),"status":"provider_required"}}
