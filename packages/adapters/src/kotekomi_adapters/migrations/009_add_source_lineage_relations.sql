CREATE TABLE IF NOT EXISTS source_lineage_relations (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);
