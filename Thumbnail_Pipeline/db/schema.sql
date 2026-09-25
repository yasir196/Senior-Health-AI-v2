PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_meta(key,value) VALUES ('schema_version','2');

CREATE TABLE IF NOT EXISTS thumbnail_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id TEXT,
  thumbnail_path TEXT NOT NULL,
  title_observed TEXT,
  thumbnail_text_observed TEXT,
  ctr_observed REAL,
  impressions_observed INTEGER,
  category_inferred TEXT,
  pattern_inferred TEXT,
  analysis_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(asset_id, thumbnail_path)
);

CREATE TABLE IF NOT EXISTS human_corrections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  thumbnail_audit_id INTEGER NOT NULL,
  field_name TEXT NOT NULL,
  original_value TEXT,
  corrected_value TEXT NOT NULL,
  value_type TEXT NOT NULL DEFAULT 'text',
  reason TEXT,
  reviewer_note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(thumbnail_audit_id) REFERENCES thumbnail_audit(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_thumbnail_audit_asset ON thumbnail_audit(asset_id);
CREATE INDEX IF NOT EXISTS idx_human_corrections_audit ON human_corrections(thumbnail_audit_id);
