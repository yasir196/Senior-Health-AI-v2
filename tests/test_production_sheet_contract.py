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
