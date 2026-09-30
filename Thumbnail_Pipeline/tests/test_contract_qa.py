from Thumbnail_Pipeline.qa.contract_qa import build_render_structure, evaluate_contract_qa


def _winner():
    return {"structural_contract":{
        "bands":[
            {"band_id":f"b{i}","reading_order":i,"x_pct":1,"y_pct":i*20,"w_pct":55,"h_pct":18,
             "hierarchy_rank":i,"wrap_policy":"inside_band_only","rotation_deg":0,"slant_deg":0,
             "alignment":"left","style_role":"band"}
            for i in range(1,5)
        ],
        "roles":[
            {"role_id":"presenter","role_type":"presenter","required":True,"x_pct":60,"y_pct":5,"w_pct":38,"h_pct":90,"saliency_rank":1,"attention_target_role_id":"target"},
            {"role_id":"target","role_type":"target","required":True,"x_pct":55,"y_pct":60,"w_pct":20,"h_pct":30,"saliency_rank":2,"attention_target_role_id":None},
        ],
        "complexity_budget":{"text_band_count":4,"max_people":1,"max_informational_objects":1,"max_attention_devices":1},
        "historical_annotations":{},
    }}


def test_contract_qa_locks_bands_and_selected_copy():
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING","boxed_keyword":"3 NIGHTTIME MISTAKES","bottom_callout":"CHECK LABEL"}
    structure=build_render_structure(_winner(),adaptation,"3 NIGHTTIME MISTAKES")
    result=evaluate_contract_qa(structure)
    assert result["verdict"]=="PASS"
    assert len(structure["text_bands"])==4
    assert all(x["rotation_deg"]==0 and x["slant_deg"]==0 for x in structure["text_bands"])


def test_contract_qa_rejects_missing_immutable_copy():
    adaptation={"top_banner":"MAGNESIUM","primary_headline":"NOT WORKING"}
    structure=build_render_structure(_winner(),adaptation,"3 NIGHTTIME MISTAKES")
    result=evaluate_contract_qa(structure)
    assert result["verdict"]=="FAIL"
    assert any("immutable selected copy" in x for x in result["findings"])
