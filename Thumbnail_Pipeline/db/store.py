from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.io_policy import safe_output

EDITABLE_FIELDS = {
    "title_observed", "thumbnail_text_observed", "category_inferred",
    "pattern_inferred", "ctr_observed", "impressions_observed",
}

def db_path() -> Path:
    return safe_output("db/thumbnail_intelligence.sqlite3")

def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn

def save_audit(record: dict[str, Any]) -> int:
    observed, inferred = record.get("observed", {}), record.get("inferred", {})
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO thumbnail_audit
            (asset_id, thumbnail_path, title_observed, thumbnail_text_observed,
             ctr_observed, impressions_observed, category_inferred, pattern_inferred, analysis_json)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (record.get("source", {}).get("asset_id"), record.get("source", {}).get("thumbnail_path"),
             observed.get("title"), observed.get("thumbnail_text_full"), observed.get("ctr"),
             observed.get("impressions"), inferred.get("category"), inferred.get("pattern_sequence"),
             json.dumps(inferred)),
        )
        return int(cur.lastrowid)

def add_correction(audit_id: int, field_name: str, corrected_value: Any, reason: str = "", reviewer_note: str = "") -> int:
    if field_name not in EDITABLE_FIELDS:
        raise ValueError(f"Field is not human-editable: {field_name}")
    with connect() as conn:
        row = conn.execute(f"SELECT {field_name} FROM thumbnail_audit WHERE id=?", (audit_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown audit id: {audit_id}")
        original = row[field_name]
        cur = conn.execute(
            """INSERT INTO human_corrections
            (thumbnail_audit_id, field_name, original_value, corrected_value, reason, reviewer_note)
            VALUES (?,?,?,?,?,?)""",
            (audit_id, field_name, None if original is None else str(original), str(corrected_value), reason, reviewer_note),
        )
        return int(cur.lastrowid)

def effective_record(audit_id: int) -> dict[str, Any]:
    with connect() as conn:
        base = conn.execute("SELECT * FROM thumbnail_audit WHERE id=?", (audit_id,)).fetchone()
        if base is None:
            raise KeyError(f"Unknown audit id: {audit_id}")
        result = dict(base)
        corrections = conn.execute(
            "SELECT * FROM human_corrections WHERE thumbnail_audit_id=? ORDER BY id", (audit_id,)
        ).fetchall()
        result["corrections"] = [dict(x) for x in corrections]
        for correction in corrections:
            result[correction["field_name"]] = correction["corrected_value"]
        return result
