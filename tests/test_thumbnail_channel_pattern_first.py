import json
import pandas as pd
import analytics_db as adb


def test_active_rules_markdown_embeds_real_matching_examples(monkeypatch, tmp_path):
    active = pd.DataFrame([{
        'feature_name':'signal_cluster','feature_value':'Text amount & hierarchy',
        'context_type':'hero_category','context_value':'food',
        'guidance_text':'Prefer testing the broader text pattern.',
        'videos':8,'total_impressions':73421,'ctr_delta_points':2.75,
        'evidence_json':json.dumps({
            'representative_signal':'text_density_bucket=>2-4 words/line',
            'supporting_signals':['text_length_bucket=11+ words','text_line_count=5']
        })
    }])
    rows = [{
        'hero_category':'food','thumbnail_text':'WHAT SENIORS SHOULD KNOW\nTHE REAL TRUTH ABOUT MILK\nBEFORE BED!',
        'text_word_count':10,'text_line_count':3,'text_density_bucket':'>2-4 words/line',
        'text_length_bucket':'8-10 words','title':'Milk title','ctr_percent':7.2,'impressions':50000,
        'presenter_position':'right','presenter_size':'medium','hero_count':1,
        'composition_layout':'text-left presenter-right','background_brightness':'dark',
        'dominant_palette':'black | white | yellow | red','text_color_scheme':'white | yellow',
        'accent_color_family':'red','contrast_level':'high','major_visual_object_count':2,
    }]
    monkeypatch.setattr(adb, 'active_channel_packaging_rules', lambda db: active)
    monkeypatch.setattr(adb, '_thumbnail_pattern_example_rows', lambda db: rows)
    md = adb.render_active_packaging_rules_markdown(tmp_path/'x.db')
    assert 'CHANNEL-PATTERN-FIRST GENERATION LOCK' in md
    assert 'WHAT SENIORS SHOULD KNOW / THE REAL TRUTH ABOUT MILK / BEFORE BED!' in md
    assert 'presenter=right' in md
    assert 'palette=black | white | yellow | red' in md
    assert 'CTR 7.20%' in md and '50,000 impressions' in md


def test_thumbnail_agent_requires_text_and_visual_pattern_first():
    text = open('Agents/Thumbnail_Agent.md', encoding='utf-8').read()
    assert 'Historical Pattern Priority' in text
    assert 'at least two options must be new topic-specific adaptations of that channel pattern' in text
    assert 'Channel Visual/Color Pattern Lock' in text
    assert 'Do not begin from generic model taste' in text
    assert 'Generic thumbnail best-practice is fallback only' in text
