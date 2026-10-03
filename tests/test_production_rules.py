from pathlib import Path

import pytest

from production_rules import DEFAULT_RULES, enabled_rules, load_rules, save_rules, validate_rules


def test_defaults_exist_without_project_file(tmp_path: Path) -> None:
    rules = load_rules(tmp_path)
    assert rules == DEFAULT_RULES
    assert {rule["scope"] for rule in rules} == {"HOOK", "BODY"}


def test_gui_rule_store_round_trip(tmp_path: Path) -> None:
    rules = load_rules(tmp_path)
    rules[0]["min_seconds"] = 3.5
    rules[0]["max_seconds"] = 4.5
    save_rules(tmp_path, rules)
    loaded = load_rules(tmp_path)
    assert loaded[0]["min_seconds"] == 3.5
    assert loaded[0]["max_seconds"] == 4.5


def test_rule_validation_rejects_invalid_duration_range() -> None:
    rules = [dict(DEFAULT_RULES[0], min_seconds=6, max_seconds=4)]
    assert any("min_seconds" in issue for issue in validate_rules(rules))


def test_enabled_rules_use_priority(tmp_path: Path) -> None:
    rules = [
        dict(DEFAULT_RULES[1], id="low", priority=10),
        dict(DEFAULT_RULES[0], id="high", priority=200),
        dict(DEFAULT_RULES[0], id="off", enabled=False, priority=999),
    ]
    save_rules(tmp_path, rules)
    assert [rule["id"] for rule in enabled_rules(tmp_path)] == ["high", "low"]
