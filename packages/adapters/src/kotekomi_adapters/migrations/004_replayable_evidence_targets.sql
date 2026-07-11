CREATE TABLE IF NOT EXISTS assertion_evidence_links (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_reanchoring_relations (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);
