CREATE TABLE IF NOT EXISTS ingestion_runs (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  source_id TEXT,
  document_id TEXT,
  representation_id TEXT,
  provenance_activity_id TEXT,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES sources(id),
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (provenance_activity_id) REFERENCES provenance_activities(id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_history
  ON ingestion_runs(started_at DESC, id DESC);
