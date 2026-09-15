"""Pre-Title checker must not render its own format block as findings.

Observed failure: an overall PASS sat above two "HIGH RISK" rows reading
"check name / short reason / exact risky span or blank", with "full suggested title"
listed as Same-DNA suggestions, and the three real rows duplicated. The checker's
stdout and stderr are concatenated, so an echoed OUTPUT FORMAT block and a repeated
answer both reach the parser.
"""

import re
from pathlib import Path

import pytest

import app

ROOT = Path(__file__).resolve().parents[1]

CONTAMINATED = """OVERALL: PASS
SUMMARY: The title uses ordinary exercise curiosity without promising a medical outcome.
CHECK|medical outcome promise|PASS|"Try" does not guarantee the exercises restore floor-sitting ability||
CHECK|age-wide instruction|PASS|"After 60" identifies the intended audience||
CHECK|disease or treatment claim|PASS|No disease, cure, prevention, or treatment implication||
CHECK|check name|PASS or REVIEW or HIGH RISK|short reason|exact risky span or blank|minimal safer wording or blank
CHECK|check name|PASS or REVIEW or HIGH RISK|short reason|exact risky span or blank|minimal safer wording or blank
SUGGESTION|full suggested title
SUGGESTION|full suggested title
OVERALL: PASS
SUMMARY: The title uses ordinary exercise curiosity without promising a medical outcome.
CHECK|medical outcome promise|PASS|"Try" does not guarantee the exercises restore floor-sitting ability||
CHECK|age-wide instruction|PASS|"After 60" identifies the intended audience||
CHECK|disease or treatment claim|PASS|No disease, cure, prevention, or treatment implication||
"""


def test_echoed_format_rows_never_render() -> None:
    result = app._extract_pre_title_response(CONTAMINATED)
    assert result["overall"] == "PASS"
    assert [c["check"] for c in result["checks"]] == [
        "medical outcome promise", "age-wide instruction", "disease or treatment claim",
    ]
    assert all(c["result"] == "PASS" for c in result["checks"])
    assert not any("check name" in c["check"] for c in result["checks"])


def test_duplicate_rows_are_collapsed() -> None:
    assert len(app._extract_pre_title_response(CONTAMINATED)["checks"]) == 3


def test_placeholder_suggestions_never_render() -> None:
    assert app._extract_pre_title_response(CONTAMINATED)["suggested_titles"] == []


def test_pass_suppresses_suggestions_per_the_checkers_own_contract() -> None:
    text = "OVERALL: PASS\nSUMMARY: fine\nSUGGESTION|A Perfectly Real Title After 60\n"
    assert app._extract_pre_title_response(text)["suggested_titles"] == []


def test_genuine_high_risk_with_evidence_survives() -> None:
    text = (
        "OVERALL: HIGH RISK\nSUMMARY: The title promises a cure.\n"
        "CHECK|cure implication|HIGH RISK|Promises reversal of a diagnosed condition"
        "|reverse your diabetes|help manage blood sugar\n"
        "SUGGESTION|3 Habits That May Help Blood Sugar After 60\n"
    )
    result = app._extract_pre_title_response(text)
    assert result["overall"] == "HIGH RISK"
    assert len(result["checks"]) == 1
    assert result["checks"][0]["risky_span"] == "reverse your diabetes"
    assert result["suggested_titles"] == ["3 Habits That May Help Blood Sugar After 60"]


def test_unevidenced_alarm_is_dropped() -> None:
    text = "OVERALL: REVIEW\nSUMMARY: x\nCHECK|vague worry|HIGH RISK|||\n"
    assert app._extract_pre_title_response(text)["checks"] == []


def test_evidenced_alarm_needs_only_a_reason_or_a_span() -> None:
    span_only = "OVERALL: REVIEW\nSUMMARY: x\nCHECK|a|HIGH RISK||cure your knees|\n"
    reason_only = "OVERALL: REVIEW\nSUMMARY: x\nCHECK|a|HIGH RISK|implies a cure||\n"
    assert len(app._extract_pre_title_response(span_only)["checks"]) == 1
    assert len(app._extract_pre_title_response(reason_only)["checks"]) == 1


def test_echoed_overall_format_line_is_not_read_as_high_risk() -> None:
    text = "OVERALL: PASS|REVIEW|HIGH RISK\nOVERALL: PASS\nSUMMARY: fine\n"
    assert app._extract_pre_title_response(text)["overall"] == "PASS"


@pytest.mark.parametrize("value", [
    "check name", "short reason", "exact risky span or blank",
    "minimal safer wording or blank", "full suggested title", "one short sentence",
    "PASS or REVIEW or HIGH RISK", "<check name>", "  Check Name  ",
])
def test_placeholder_detector_catches_template_tokens(value: str) -> None:
    assert app._is_pre_title_placeholder(value)


@pytest.mark.parametrize("value", [
    "medical outcome promise", "age-wide instruction", "PASS", "HIGH RISK",
    "reverse your diabetes", "Try These 3 Simple Exercises After 60",
])
def test_placeholder_detector_leaves_real_content_alone(value: str) -> None:
    assert not app._is_pre_title_placeholder(value)


def test_json_responses_are_sanitized_too() -> None:
    raw = (
        '{"overall": "PASS", "summary": "fine", "checks": ['
        '{"check": "check name", "result": "HIGH RISK", "reason": "short reason",'
        ' "risky_span": "exact risky span or blank", "suggested_wording": ""},'
        '{"check": "real check", "result": "PASS", "reason": "a real reason",'
        ' "risky_span": "", "suggested_wording": ""}],'
        ' "suggested_titles": ["full suggested title"]}'
    )
    result = app._extract_pre_title_response(raw)
    assert [c["check"] for c in result["checks"]] == ["real check"]
    assert result["suggested_titles"] == []


def test_every_placeholder_in_the_shipped_prompt_is_covered() -> None:
    """Closed loop: the prompt cannot introduce a placeholder the parser won't catch."""
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    block = re.search(r"OUTPUT FORMAT[^\n]*\n(.*?)\n\"\"\"", source, re.S)
    assert block, "pre-title OUTPUT FORMAT block not found"
    tokens = re.findall(r"<([^<>|]+)>", block.group(1))
    uncovered = [
        token for token in tokens
        if not app._is_pre_title_placeholder(token)
        and token.strip().casefold() not in {"pass", "review", "high risk"}
    ]
    assert not uncovered, f"prompt placeholders the parser would accept as findings: {uncovered}"
