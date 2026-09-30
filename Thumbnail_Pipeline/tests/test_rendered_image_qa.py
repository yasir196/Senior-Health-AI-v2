from Thumbnail_Pipeline.qa.rendered_image_qa import evaluate_rendered_image_qa


def _expected():
    return {
        "text_bands":[
            {"text":"MAGNESIUM","x_pct":4,"y_pct":6,"w_pct":56,"h_pct":22},
            {"text":"3 NIGHTTIME MISTAKES","x_pct":4,"y_pct":30,"w_pct":56,"h_pct":18},
        ],
        "visual_placements":[
            {"role_id":"target","kind":"informational_object","is_primary_target":True},
        ],
        "complexity_budget":{"max_people":1,"max_informational_objects":1,"max_attention_devices":1},
    }


def _observed():
    return {
        "text_bands":[
            {"text":"MAGNESIUM","x_pct":4,"y_pct":6,"w_pct":56,"h_pct":22,"rotation_deg":0,"slant_deg":0},
            {"text":"3 NIGHTTIME MISTAKES","x_pct":4,"y_pct":30,"w_pct":56,"h_pct":18,"rotation_deg":0,"slant_deg":0},
        ],
        "people_count":1,"informational_object_count":1,"attention_device_count":1,
        "primary_target_role_id":"target","attention_target_role_id":"target",
        "extra_visible_text":[],"extra_informational_objects":[],"timestamp_safe_zone_clear":True,
    }


def test_phase2_pixel_contract_passes_matching_observation():
    assert evaluate_rendered_image_qa(_expected(),_observed())["verdict"]=="PASS"


def test_phase2_rejects_text_slant_and_extra_object():
    obs=_observed()
    obs["text_bands"][0]["slant_deg"]=7
    obs["informational_object_count"]=2
    obs["extra_informational_objects"]=["diary"]
    result=evaluate_rendered_image_qa(_expected(),obs)
    assert result["verdict"]=="FAIL"
    assert any("glyph slant" in x for x in result["findings"])
    assert any("exceeds budget" in x for x in result["findings"])
    assert "extra informational objects detected" in result["findings"]


def test_phase2_rejects_wrong_attention_target_and_safe_zone():
    obs=_observed()
    obs["attention_target_role_id"]="other"
    obs["timestamp_safe_zone_clear"]=False
    result=evaluate_rendered_image_qa(_expected(),obs)
    assert result["verdict"]=="FAIL"
    assert any("attention mapping mismatch" in x for x in result["findings"])
    assert "bottom-right timestamp safe zone is not clear" in result["findings"]
