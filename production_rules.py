from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

RULES_FILENAME = "production_rules.json"

DEFAULT_RULES: list[dict[str, Any]] = [
    {"id": "hook_image_duration", "name": "Hook image duration", "category": "IMAGE", "scope": "HOOK", "enabled": True, "priority": 200, "hard": True, "min_seconds": 4.0, "max_seconds": 5.0},
    {"id": "normal_image_duration", "name": "Normal image duration", "category": "IMAGE", "scope": "BODY", "enabled": True, "priority": 100, "hard": True, "min_seconds": 7.0, "max_seconds": 8.0},
]


def rules_path(project: Path) -> Path:
    return Path(project) / RULES_FILENAME


def normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(rule.get("id") or "").strip(),
        "name": str(rule.get("name") or "").strip(),
        "category": str(rule.get("category") or "IMAGE").strip().upper(),
        "scope": str(rule.get("scope") or "ALL").strip().upper(),
        "enabled": bool(rule.get("enabled", True)),
        "priority": int(rule.get("priority", 100)),
        "hard": bool(rule.get("hard", True)),
        "min_seconds": float(rule.get("min_seconds", 0.0)),
        "max_seconds": float(rule.get("max_seconds", 0.0)),
    }


def validate_rules(rules: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(rules, 1):
        rule = normalize_rule(raw)
        rid = rule["id"]
        if not rid:
            issues.append(f"Rule {index}: id is required.")
        elif rid in seen:
            issues.append(f"Rule {index}: duplicate id {rid!r}.")
        seen.add(rid)
        if not rule["name"]:
            issues.append(f"Rule {index}: name is required.")
        if rule["min_seconds"] < 0 or rule["max_seconds"] < 0:
            issues.append(f"{rid or index}: durations cannot be negative.")
        if rule["max_seconds"] and rule["min_seconds"] > rule["max_seconds"]:
            issues.append(f"{rid or index}: min_seconds cannot exceed max_seconds.")
    return issues


def load_rules(project: Path) -> list[dict[str, Any]]:
    path = rules_path(project)
    if not path.is_file():
        return [dict(rule) for rule in DEFAULT_RULES]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [dict(rule) for rule in DEFAULT_RULES]
    raw_rules = payload.get("rules", []) if isinstance(payload, dict) else []
    return [normalize_rule(rule) for rule in raw_rules if isinstance(rule, dict)]


def save_rules(project: Path, rules: list[dict[str, Any]]) -> Path:
    normalized = [normalize_rule(rule) for rule in rules]
    issues = validate_rules(normalized)
    if issues:
        raise ValueError("\n".join(issues))
    path = rules_path(project)
    payload = {
        "version": 1,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "rules": normalized,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def enabled_rules(project: Path) -> list[dict[str, Any]]:
    return sorted(
        (rule for rule in load_rules(project) if rule["enabled"]),
        key=lambda rule: (-int(rule["priority"]), rule["id"]),
    )
