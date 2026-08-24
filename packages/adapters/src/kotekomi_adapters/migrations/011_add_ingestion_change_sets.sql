CREATE TABLE IF NOT EXISTS ingestion_change_sets (
  id TEXT PRIMARY KEY,
  ingestion_run_id TEXT NOT NULL UNIQUE,
  analysis_run_id TEXT NOT NULL,
  representation_id TEXT NOT NULL,
  closed_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id),
  FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id),
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_change_sets_analysis_run
  ON ingestion_change_sets(analysis_run_id);
