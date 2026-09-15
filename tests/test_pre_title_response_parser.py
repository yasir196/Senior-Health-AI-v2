import json
import re
from pathlib import Path
from typing import Any

APP = Path(__file__).resolve().parents[1] / "app.py"
source = APP.read_text(encoding="utf-8")
start = source.index("def _normalize_pre_title_payload")
end = source.index("def _run_pre_title_check", start)
ns = {"json": json, "re": re, "Any": Any}
exec(source[start:end], ns)
extract = ns["_extract_pre_title_response"]

PAYLOAD = {
    "overall": "REVIEW",
    "summary": "Timing wording needs review.",
    "checks": [{"check": "Timing", "result": "REVIEW", "reason": "x", "risky_span": "morning", "suggested_wording": "routine"}],
    "suggested_titles": ["A", "B", "C"],
}

def test_plain_json():
    assert extract(json.dumps(PAYLOAD))["overall"] == "REVIEW"

def test_markdown_fence_and_noise():
    raw = "analysis text\n```json\n" + json.dumps(PAYLOAD) + "\n```\ntokens used: 10"
    assert extract(raw)["summary"] == PAYLOAD["summary"]

def test_unrelated_json_before_and_after():
    raw = json.dumps({"event":"start"}) + "\n" + json.dumps(PAYLOAD) + "\n" + json.dumps({"event":"done"})
    assert extract(raw)["suggested_titles"] == ["A","B","C"]

def test_nested_codex_event_string():
    raw = json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps(PAYLOAD)}})
    assert extract(raw)["overall"] == "REVIEW"

def test_line_protocol():
    raw = """Codex startup noise
OVERALL: REVIEW
SUMMARY: Morning timing needs review.
CHECK|Timing|REVIEW|No special timing is established|morning|routine
CHECK|Audience|PASS|Audience framing is acceptable|||
SUGGESTION|Over 60? Consider This 1 Drink for Your Muscle-Support Routine
SUGGESTION|Over 60? This 1 Drink May Support Your Nutrition Routine
SUGGESTION|Over 60? What This 1 Drink Adds to a Muscle-Support Routine
tokens used 123
"""
    got=extract(raw)
    assert got["overall"] == "REVIEW"
    assert len(got["checks"]) == 2
    assert len(got["suggested_titles"]) == 3

def test_markdown_fallback():
    raw = """## Verdict: HIGH RISK
**Summary:** The claim is too strong.
### Suggested Titles
1. Safer title A
2. Safer title B
3. Safer title C
"""
    got=extract(raw)
    assert got["overall"] == "HIGH RISK"
    assert got["suggested_titles"] == ["Safer title A", "Safer title B", "Safer title C"]

def test_status_and_alias_keys_json():
    raw=json.dumps({"status":"PASS","reason":"Looks okay","issues":[],"suggestions":[]})
    got=extract(raw)
    assert got["overall"] == "PASS"
    assert got["summary"] == "Looks okay"
