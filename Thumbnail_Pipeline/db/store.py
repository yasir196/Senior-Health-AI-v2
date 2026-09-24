from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.io_policy import safe_output

SCHEMA_VERSION=2
EDITABLE_FIELDS={"title_observed","thumbnail_text_observed","category_inferred","pattern_inferred","ctr_observed","impressions_observed"}
NUMERIC_FIELDS={"ctr_observed":float,"impressions_observed":int}

def db_path()->Path: return safe_output("db/thumbnail_intelligence.sqlite3")

def _migrate(conn:sqlite3.Connection)->None:
    cols={r[1] for r in conn.execute("PRAGMA table_info(human_corrections)")}
    if cols and "value_type" not in cols:
        conn.execute("ALTER TABLE human_corrections ADD COLUMN value_type TEXT NOT NULL DEFAULT 'text'")
    conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    conn.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version',?)",(str(SCHEMA_VERSION),))
    duplicates=conn.execute("""SELECT COALESCE(asset_id,''),thumbnail_path,MIN(id) keep_id FROM thumbnail_audit GROUP BY COALESCE(asset_id,''),thumbnail_path HAVING COUNT(*)>1""").fetchall()
    for asset_key,thumb,keep_id in duplicates:
        extra=conn.execute("SELECT id FROM thumbnail_audit WHERE COALESCE(asset_id,'')=? AND thumbnail_path=? AND id<>?",(asset_key,thumb,keep_id)).fetchall()
        for row in extra:
            conn.execute("UPDATE human_corrections SET thumbnail_audit_id=? WHERE thumbnail_audit_id=?",(keep_id,row[0]))
            conn.execute("DELETE FROM thumbnail_audit WHERE id=?",(row[0],))
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_thumbnail_audit_identity_strict ON thumbnail_audit(COALESCE(asset_id,''),thumbnail_path)")

def connect()->sqlite3.Connection:
    path=db_path(); path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path); conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
    _migrate(conn)
    return conn

def _jsonable(v:Any)->Any:
    return json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list,tuple)) else v

def save_audit(record:dict[str,Any])->int:
    observed,inferred=record.get("observed",{}),record.get("inferred",{})
    extracted=record.get("extracted",{})
    source=record.get("source",{}); asset_id=source.get("asset_id"); thumb=source.get("thumbnail_path")
    if not thumb: raise ValueError("thumbnail_path is required")
    vals=(asset_id,thumb,observed.get("title"),extracted.get("thumbnail_text_full",observed.get("thumbnail_text_full")),observed.get("ctr"),observed.get("impressions"),inferred.get("category"),_jsonable(inferred.get("pattern_sequence")),json.dumps(inferred,ensure_ascii=False,sort_keys=True))
    with connect() as conn:
        existing=conn.execute("SELECT id FROM thumbnail_audit WHERE asset_id IS ? AND thumbnail_path=?",(asset_id,thumb)).fetchone()
        if existing:
            conn.execute("""UPDATE thumbnail_audit SET title_observed=?,thumbnail_text_observed=?,ctr_observed=?,impressions_observed=?,category_inferred=?,pattern_inferred=?,analysis_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",vals[2:]+(int(existing["id"]),))
            return int(existing["id"])
        cur=conn.execute("""INSERT INTO thumbnail_audit(asset_id,thumbnail_path,title_observed,thumbnail_text_observed,ctr_observed,impressions_observed,category_inferred,pattern_inferred,analysis_json) VALUES(?,?,?,?,?,?,?,?,?)""",vals)
        return int(cur.lastrowid)

def _encode(field:str,value:Any)->tuple[str,str]:
    if field=="impressions_observed":
        value=int(value); return str(value),"int"
    if field=="ctr_observed":
        value=float(value); return repr(value),"float"
    if isinstance(value,(dict,list,tuple)): return json.dumps(value,ensure_ascii=False,sort_keys=True),"json"
    return str(value),"text"

def _decode(value:str|None,value_type:str)->Any:
    if value is None:return None
    if value_type=="int":return int(value)
    if value_type=="float":return float(value)
    if value_type=="json":return json.loads(value)
    return value

def add_correction(audit_id:int,field_name:str,corrected_value:Any,reason:str="",reviewer_note:str="")->int:
    if field_name not in EDITABLE_FIELDS: raise ValueError(f"Field is not human-editable: {field_name}")
    encoded,value_type=_encode(field_name,corrected_value)
    with connect() as conn:
        row=conn.execute(f"SELECT {field_name} FROM thumbnail_audit WHERE id=?",(audit_id,)).fetchone()
        if row is None: raise KeyError(f"Unknown audit id: {audit_id}")
        original=row[field_name]
        cur=conn.execute("""INSERT INTO human_corrections(thumbnail_audit_id,field_name,original_value,corrected_value,value_type,reason,reviewer_note) VALUES(?,?,?,?,?,?,?)""",(audit_id,field_name,None if original is None else str(original),encoded,value_type,reason,reviewer_note))
        conn.execute("UPDATE thumbnail_audit SET updated_at=CURRENT_TIMESTAMP WHERE id=?",(audit_id,))
        return int(cur.lastrowid)

def effective_record(audit_id:int)->dict[str,Any]:
    with connect() as conn:
        base=conn.execute("SELECT * FROM thumbnail_audit WHERE id=?",(audit_id,)).fetchone()
        if base is None: raise KeyError(f"Unknown audit id: {audit_id}")
        result=dict(base); corrections=conn.execute("SELECT * FROM human_corrections WHERE thumbnail_audit_id=? ORDER BY id",(audit_id,)).fetchall()
        result["corrections"]=[dict(x) for x in corrections]
        for c in corrections: result[c["field_name"]]=_decode(c["corrected_value"],c["value_type"])
        return result
