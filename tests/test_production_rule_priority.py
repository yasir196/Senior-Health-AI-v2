from production_timing_controller import resolve_rule, resolve_scope


def test_section_override_beats_global_fallback() -> None:
    rules = [
        {"id": "global", "category": "IMAGE", "scope": "ALL", "priority": 999},
        {"id": "hook", "category": "IMAGE", "scope": "HOOK", "priority": 100},
    ]
    assert resolve_rule(rules, "HOOK")["id"] == "hook"


def test_higher_priority_wins_inside_same_section() -> None:
    rules = [
        {"id": "low", "category": "IMAGE", "scope": "EVIDENCE", "priority": 100},
        {"id": "high", "category": "IMAGE", "scope": "EVIDENCE", "priority": 300},
    ]
    assert resolve_rule(rules, "EVIDENCE")["id"] == "high"


def test_explicit_section_beats_time_based_hook() -> None:
    assert resolve_scope({"scope": "EVIDENCE", "Transcript Text": "study details"}, 5.0, {}) == "EVIDENCE"
    assert resolve_scope({"Section": "CTA", "Transcript Text": "closing action"}, 5.0, {}) == "CTA"
