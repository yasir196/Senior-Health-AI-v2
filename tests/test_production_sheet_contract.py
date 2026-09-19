from __future__ import annotations
import csv
from pathlib import Path
from production_sheet_contract import PRODUCTION_SHEET_COLUMNS, normalize_production_sheet, validate_scene_segmentation


def test_compact_sheet_normalizes_to_canonical_32_columns_and_preserves_ai_count(tmp_path: Path):
    p=tmp_path/'07_production_sheet.csv'
    fields=['scene_id','slot_type','asset_id','image_filename','start_time','end_time','duration_seconds','script_excerpt','discourse_role','narrative_context','visual_intent','alignment_score','qa_status']
    rows=[]
    kinds=['AVATAR']*4+['AI_IMAGE']*3+['OVERLAY']*2+['STOCK']
    with p.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        for i,k in enumerate(kinds,1):
            w.writerow({'scene_id':str(i),'slot_type':k,'start_time':f'00:{i:02d}','end_time':f'00:{i+1:02d}','duration_seconds':'1','script_excerpt':f'Line {i}.','discourse_role':'CONTENT','narrative_context':f'Context {i}','visual_intent':f'older adult performs concrete action {i}'})
    ok,issues=normalize_production_sheet(p)
    assert ok,issues
    with p.open(encoding='utf-8-sig',newline='') as h:
        r=csv.DictReader(h); out=list(r); assert r.fieldnames==PRODUCTION_SHEET_COLUMNS
    assert len(PRODUCTION_SHEET_COLUMNS)==32
    ai=[x for x in out if x['recommended_asset_type']=='AI_IMAGE']
    assert len(ai)==3
    assert [x['image_prompt_id'] for x in ai]==['IMG001','IMG002','IMG003']
    assert all(x['ai_image_prompt'] for x in ai)
    stock=[x for x in out if x['recommended_asset_type']=='STOCK_VIDEO']
    assert len(stock)==1 and stock[0]['broll_prompt_id']=='BR001'
    assert stock[0]['asset_search_query']


def test_canonical_header_is_frozen():
    assert len(PRODUCTION_SHEET_COLUMNS)==32
    assert PRODUCTION_SHEET_COLUMNS[0]=='scene_id'
    assert PRODUCTION_SHEET_COLUMNS[-1]=='notes'
    assert 'recommended_asset_type' in PRODUCTION_SHEET_COLUMNS
    assert 'image_prompt_id' in PRODUCTION_SHEET_COLUMNS



def _segmentation_row(scene_id: str, excerpt: str, *, notes: str = "", duration: str = "4.00") -> dict[str, str]:
    return {
        "scene_id": scene_id,
        "script_excerpt": excerpt,
        "notes": notes,
        "recommended_asset_type": "AVATAR",
        "start_time": "0:00",
        "end_time": "0:04",
        "duration_sec": duration,
    }


def test_tiny_fragment_is_a_segmentation_violation_unless_intentional_emphasis():
    tiny = _segmentation_row("S003", "Just five.", duration="1.50")
    issues = validate_scene_segmentation([tiny])
    assert any("S003: script_excerpt has only 2 words" in issue for issue in issues)

    intentional = _segmentation_row(
        "S003", "Just five.", notes="INTENTIONAL_EMPHASIS", duration="1.50"
    )
    issues = validate_scene_segmentation([intentional])
    assert not any("script_excerpt has only" in issue for issue in issues)


def test_normal_semantic_scene_passes_segmentation_gate():
    row = _segmentation_row(
        "S004",
        "Start with five controlled repetitions and notice how the movement feels today.",
        duration="5.00",
    )
    assert validate_scene_segmentation([row]) == []


def test_production_agent_requires_zero_validator_equivalent_issues_before_write():
    agent = (ROOT / "Agents" / "Production_Agent.md").read_text(encoding="utf-8")

    assert "Treat this as a generation hard gate, not a downstream warning" in agent
    assert "production_sheet_contract.validate_scene_segmentation" in agent
    assert "ordinary excerpts under 4 words = 0" in agent
    assert "narration-duration plausibility violations = 0" in agent
    assert "validate again" in agent


def test_production_agent_requires_final_exact_narration_provenance_gate():
    agent = (Path(__file__).resolve().parents[1] / "Agents" / "Production_Agent.md").read_text(encoding="utf-8")
    assert "FINAL NARRATION-PROVENANCE GATE" in agent
    assert "re-read the current `06a_voice_script.md` from disk" in agent
    assert "every final `script_excerpt` must be found as one contiguous excerpt" in agent
    assert "provenance issues = 0 and segmentation/timing issues = 0" in agent
    assert "Never weaken or bypass downstream Avatar Timing source validation" in agent


def test_app_runs_deterministic_provenance_gate_immediately_after_production():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "source_ok, source_issues = validate_production_sheet_against_voice(project)" in app
    assert "segmentation_issues = production_sheet_segmentation_issues(project)" in app
    assert "Production final deterministic gate: FAIL" in app
    assert "07_production_sheet.csv is NOT PRODUCTION READY" in app


def test_asset_distribution_rejects_quota_blocks_and_missing_configured_lane():
    from production_sheet_contract import validate_asset_distribution
    rows = (
        [{"scene_id": f"S{i:03d}", "recommended_asset_type": "AVATAR"} for i in range(1, 11)]
        + [{"scene_id": f"S{i:03d}", "recommended_asset_type": "AI_IMAGE"} for i in range(11, 18)]
        + [{"scene_id": f"S{i:03d}", "recommended_asset_type": "OVERLAY"} for i in range(18, 26)]
    )
    issues = validate_asset_distribution(
        rows, {"avatar": 40, "ai_images": 30, "stock": 10, "overlays": 20}
    )
    assert any("consecutive avatar scenes" in issue for issue in issues)
    assert any("consecutive ai_images scenes" in issue for issue in issues)
    assert any("no stock scenes were assigned" in issue for issue in issues)


def test_asset_distribution_accepts_interleaved_approximate_mix():
    from production_sheet_contract import validate_asset_distribution
    pattern = ["AVATAR", "AI_IMAGE", "AVATAR", "OVERLAY", "STOCK_VIDEO",
               "AVATAR", "AI_IMAGE", "OVERLAY", "AVATAR", "AI_IMAGE"]
    rows = [
        {"scene_id": f"S{i:03d}", "recommended_asset_type": pattern[(i - 1) % len(pattern)]}
        for i in range(1, 101)
    ]
    assert validate_asset_distribution(
        rows, {"avatar": 40, "ai_images": 30, "stock": 10, "overlays": 20}
    ) == []


def test_app_final_production_gate_checks_asset_distribution():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "production_sheet_asset_distribution_issues(project)" in app
    assert "Asset distribution:" in app
    assert "distribution_issues" in app


def test_production_agent_forbids_block_allocated_asset_mix():
    agent = (Path(__file__).resolve().parents[1] / "Agents" / "Production_Agent.md").read_text(encoding="utf-8")
    assert "TIMELINE distribution, not a quota-block allocation" in agent
    assert "all AVATAR scenes first" in agent
    assert "CURRENT saved `production_settings.json`" in agent
    assert "0% lane must not be forced" in agent
    assert "within ±5 percentage points" in agent


def test_asset_distribution_respects_user_zero_percent_lane():
    from production_sheet_contract import validate_asset_distribution
    pattern = ["AVATAR", "AI_IMAGE", "OVERLAY", "AVATAR", "AI_IMAGE",
               "OVERLAY", "AVATAR", "AI_IMAGE", "OVERLAY", "AVATAR",
               "AI_IMAGE", "OVERLAY", "AVATAR", "AI_IMAGE", "AVATAR",
               "OVERLAY", "AVATAR", "AI_IMAGE", "OVERLAY", "AVATAR"]
    rows = [
        {"scene_id": f"S{i:03d}", "recommended_asset_type": pattern[(i - 1) % len(pattern)]}
        for i in range(1, 101)
    ]
    assert validate_asset_distribution(
        rows, {"avatar": 40, "ai_images": 35, "stock": 0, "overlays": 25}
    ) == []


def test_asset_distribution_allows_user_selected_single_lane_100_percent():
    from production_sheet_contract import validate_asset_distribution
    rows = [
        {"scene_id": f"S{i:03d}", "recommended_asset_type": "AVATAR"}
        for i in range(1, 51)
    ]
    assert validate_asset_distribution(
        rows, {"avatar": 100, "ai_images": 0, "stock": 0, "overlays": 0}
    ) == []


def test_asset_sequence_rejects_mechanical_short_template_tiling():
    from production_sheet_contract import validate_asset_sequence_naturalness
    pattern = ["AVATAR", "AVATAR", "AI_IMAGE", "OVERLAY", "OVERLAY"]
    rows = [
        {"scene_id": f"S{i:03d}", "recommended_asset_type": pattern[(i - 1) % len(pattern)]}
        for i in range(1, 61)
    ]
    issues = validate_asset_sequence_naturalness(rows)
    assert any("mechanical" in issue and "5-scene template" in issue for issue in issues)


def test_asset_sequence_allows_nonperiodic_semantic_mix():
    from production_sheet_contract import validate_asset_sequence_naturalness
    sequence = [
        "AVATAR","AI_IMAGE","OVERLAY","AVATAR","AVATAR","OVERLAY","AI_IMAGE","AVATAR",
        "OVERLAY","AI_IMAGE","AVATAR","OVERLAY","AVATAR","AI_IMAGE","AI_IMAGE","OVERLAY",
        "AVATAR","AI_IMAGE","OVERLAY","OVERLAY","AVATAR","AI_IMAGE","AVATAR","OVERLAY",
        "AI_IMAGE","AVATAR","OVERLAY","AI_IMAGE","AVATAR","AVATAR",
    ]
    rows = [{"scene_id": f"S{i:03d}", "recommended_asset_type": asset} for i, asset in enumerate(sequence, 1)]
    assert validate_asset_sequence_naturalness(rows) == []


def test_avatar_timing_no_longer_treats_bad_segmentation_as_timing_only_warning():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "scene segmentation/timing FAILED" in app
    assert "transcript timing cannot repair invalid scene boundaries" in app
    assert "Avatar timing may continue because real transcript timing" not in app


def test_production_agent_requires_final_literal_row_segmentation_validation():
    agent = (Path(__file__).resolve().parents[1] / "Agents" / "Production_Agent.md").read_text(encoding="utf-8")
    assert "POST-ASSET SEGMENTATION GATE" in agent
    assert "FINAL literal `script_excerpt` strings" in agent
    assert "deterministic validator itself returns an empty issue list" in agent
    assert "repeating percentage template" in agent
