from Thumbnail_Pipeline.qa.contract_qa import build_render_structure, evaluate_contract_qa
from Thumbnail_Pipeline.adapters.winner_metadata import _repair_presenter_role_binding, _enforce_visual_complexity_budget


def _winner():
    return {"structural_contract":{
        "bands":[
            {"band_id":f"b{i}","reading_order":i,"x_pct":1,"y_pct":i*15,"w_pct":55 if i<4 else 27,"h_pct":14,
             "hierarchy_rank":i,"wrap_policy":"inside_band_only","rotation_deg":0,"slant_deg":0,
             "alignment":"left","style_role":"band"}
            for i in range(1,6)
        ],
        "roles":[
            {"role_id":"presenter","role_type":"presenter","required":True,"x_pct":60,"y_pct":5,"w_pct":38,"h_pct":90,"saliency_rank":1,"attention_target_role_id":"target"},
            {"role_id":"target","role_type":"target","required":True,"x_pct":55,"y_pct":60,"w_pct":20,"h_pct":30,"saliency_rank":2,"attention_target_role_id":None},
            {"role_id":"attention","role_type":"attention_device","required":True,"x_pct":55,"y_pct":60,"w_pct":20,"h_pct":30,"saliency_rank":3,"attention_target_role_id":"target"},
            {"role_id":"chair","role_type":"support/chair","required":False,"x_pct":60,"y_pct":30,"w_pct":25,"h_pct":50,"saliency_rank":4,"attention_target_role_id":None},
        ],
        "complexity_budget":{"text_band_count":5,"max_people":1,"max_informational_objects":1,"max_attention_devices":1},
        "historical_annotations":{},
    }}


def _placements(extra=None):
    rows=[
        {"placement_id":"p","role_id":"presenter","kind":"person","description":"neutral presenter","is_primary_target":False,"attention_target_role_id":None},
        {"placement_id":"m","role_id":"target","kind":"informational_object","description":"one magnesium bottle","is_primary_target":True,"attention_target_role_id":None},
        {"placement_id":"a","role_id":"attention","kind":"attention_device","description":"one curved arrow","is_primary_target":False,"attention_target_role_id":"target"},
    ]
    return rows+(extra or [])


def test_contract_qa_splits_explicit_cta_across_consecutive_bands():
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements()}
    structure=build_render_structure(_winner(),adaptation,"3 NIGHTTIME MISTAKES")
    result=evaluate_contract_qa(structure)
    assert result["verdict"]=="PASS"
    assert [x["text"] for x in structure["text_bands"]]==["MAGNESIUM","NOT WORKING","3 NIGHTTIME MISTAKES","DO","THIS"]
    assert structure["text_bands"][3]["segment_index"]==0
    assert structure["text_bands"][4]["segment_index"]==1


def test_immutable_copy_never_splits_even_if_it_contains_marker():
    selected="DO | THIS"
    adaptation={"top_banner":"MAGNESIUM","primary_headline":selected,"visual_placements":_placements()}
    structure=build_render_structure(_winner(),adaptation,selected)
    assert structure["text_bands"][1]["text"]==selected
    assert structure["text_bands"][1]["segment_index"] is None


def test_contract_qa_rejects_unbound_or_over_budget_objects():
    extra=[
        {"placement_id":"rx","role_id":"missing","kind":"informational_object","description":"prescription bottle","is_primary_target":False,"attention_target_role_id":None},
        {"placement_id":"diary","role_id":"chair","kind":"informational_object","description":"sleep diary","is_primary_target":False,"attention_target_role_id":None},
    ]
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements(extra)}
    structure=build_render_structure(_winner(),adaptation,"3 NIGHTTIME MISTAKES")
    result=evaluate_contract_qa(structure)
    assert result["verdict"]=="FAIL"
    assert any("exceed winner budget" in x for x in result["findings"])
    assert any("no winner role binding" in x for x in result["findings"])
    assert any("cannot bind" in x for x in result["findings"])


def test_presenter_and_chair_do_not_consume_informational_object_budget():
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements([
        {"placement_id":"c","role_id":"chair","kind":"support","description":"chair","is_primary_target":False,"attention_target_role_id":None}
    ])}
    result=evaluate_contract_qa(build_render_structure(_winner(),adaptation,"3 NIGHTTIME MISTAKES"))
    assert result["verdict"]=="PASS"


def test_environment_cannot_be_used_as_informational_object_role():
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements([
        {"placement_id":"diary","role_id":"chair","kind":"informational_object","description":"sleep diary hidden in support","is_primary_target":False,"attention_target_role_id":None}
    ])}
    result=evaluate_contract_qa(build_render_structure(_winner(),adaptation,"3 NIGHTTIME MISTAKES"))
    assert result["verdict"]=="FAIL"
    assert any("cannot bind" in x for x in result["findings"])


def test_text_stack_visual_placement_fails_loudly():
    winner=_winner()
    winner["structural_contract"]["roles"].append(
        {"role_id":"text_stack","role_type":"text_stack","required":True,"x_pct":1,"y_pct":1,"w_pct":55,"h_pct":70,"saliency_rank":1,"attention_target_role_id":None}
    )
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements([
        {"placement_id":"txt","role_id":"text_stack","kind":"informational_object","description":"duplicate text stack","is_primary_target":False,"attention_target_role_id":None}
    ])}
    result=evaluate_contract_qa(build_render_structure(winner,adaptation,"3 NIGHTTIME MISTAKES"))
    assert result["verdict"]=="FAIL"
    assert any("text roles are never informational objects; visible text is governed solely by TEXT BANDS JSON" in x for x in result["findings"])


def test_text_stack_role_needs_no_visual_placement():
    winner=_winner()
    winner["structural_contract"]["roles"].append(
        {"role_id":"text_stack","role_type":"text_stack","required":True,"x_pct":1,"y_pct":1,"w_pct":55,"h_pct":70,"saliency_rank":1,"attention_target_role_id":None}
    )
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements()}
    result=evaluate_contract_qa(build_render_structure(winner,adaptation,"3 NIGHTTIME MISTAKES"))
    assert result["verdict"]=="PASS"


def _winner_with_text_stack():
    winner=_winner()
    winner["structural_contract"]["roles"].append(
        {"role_id":"text_stack","role_type":"text_stack","required":False,"x_pct":1,"y_pct":1,"w_pct":55,"h_pct":70,"saliency_rank":4,"attention_target_role_id":None}
    )
    return winner


def test_text_stack_informational_object_placement_fails_loudly():
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements([
        {"placement_id":"txt","role_id":"text_stack","kind":"informational_object","description":"duplicate text stack","is_primary_target":False,"attention_target_role_id":None}
    ])}
    result=evaluate_contract_qa(build_render_structure(_winner_with_text_stack(),adaptation,"3 NIGHTTIME MISTAKES"))
    assert result["verdict"]=="FAIL"
    assert any("text roles are never informational objects; visible text is governed solely by TEXT BANDS JSON" in x for x in result["findings"])


def test_text_stack_role_needs_no_visual_placement():
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"DO | THIS","visual_placements":_placements()}
    result=evaluate_contract_qa(build_render_structure(_winner_with_text_stack(),adaptation,"3 NIGHTTIME MISTAKES"))
    assert result["verdict"]=="PASS"


def test_presenter_binding_repairs_single_unambiguous_people_role():
    winner=_winner()
    adaptation={"visual_placements":[
        {"placement_id":"placement_presenter_1","role_id":"target","kind":"person","description":"neutral presenter","is_primary_target":False,"attention_target_role_id":None},
        {"placement_id":"m","role_id":"target","kind":"informational_object","description":"socked foot","is_primary_target":True,"attention_target_role_id":None},
    ]}
    repaired=_repair_presenter_role_binding(winner,adaptation)
    assert repaired["visual_placements"][0]["role_id"]=="presenter"
    assert repaired["visual_placements"][1]["role_id"]=="target"


def test_presenter_binding_does_not_guess_between_multiple_people_roles():
    winner=_winner()
    winner["structural_contract"]["roles"].append(
        {"role_id":"person_2","role_type":"person","required":False,"x_pct":70,"y_pct":5,"w_pct":20,"h_pct":80,"saliency_rank":2,"attention_target_role_id":None}
    )
    adaptation={"visual_placements":[
        {"placement_id":"placement_presenter_1","role_id":"target","kind":"person","description":"neutral presenter","is_primary_target":False,"attention_target_role_id":None}
    ]}
    repaired=_repair_presenter_role_binding(winner,adaptation)
    assert repaired["visual_placements"][0]["role_id"]=="target"


def test_visual_budget_preflight_drops_second_informational_object():
    winner=_winner()
    adaptation={"secondary_detail":"row of five exercise icons","visual_placements":[
        {"placement_id":"target","role_id":"target","kind":"informational_object","description":"socked foot","is_primary_target":True,"attention_target_role_id":None},
        {"placement_id":"icons","role_id":"target","kind":"informational_object","description":"five exercise icons","is_primary_target":False,"attention_target_role_id":None},
    ]}
    repaired=_enforce_visual_complexity_budget(winner,adaptation)
    objects=[x for x in repaired["visual_placements"] if x["kind"]=="informational_object"]
    assert len(objects)==1
    assert objects[0]["placement_id"]=="target"
    assert repaired["secondary_detail"] is None


def test_visual_budget_preflight_preserves_noninformational_support():
    winner=_winner()
    adaptation={"visual_placements":[
        {"placement_id":"target","role_id":"target","kind":"informational_object","description":"socked foot","is_primary_target":True,"attention_target_role_id":None},
        {"placement_id":"chair","role_id":"chair","kind":"support","description":"stable chair","is_primary_target":False,"attention_target_role_id":None},
    ]}
    repaired=_enforce_visual_complexity_budget(winner,adaptation)
    assert [x["placement_id"] for x in repaired["visual_placements"]]==["target","chair"]


def test_presenter_role_repair_accepts_unambiguous_presenter_role_id():
    metadata={
        "structural_contract":{
            "roles":[
                {"role_id":"presenter_anchor","role_type":"photographic_subject"},
                {"role_id":"target_foot","role_type":"support/target"},
            ]
        }
    }
    adaptation={"visual_placements":[
        {"placement_id":"presenter_01","role_id":"target_foot","kind":"person"}
    ]}
    repaired=_repair_presenter_role_binding(metadata,adaptation)
    assert repaired["visual_placements"][0]["role_id"]=="presenter_anchor"
