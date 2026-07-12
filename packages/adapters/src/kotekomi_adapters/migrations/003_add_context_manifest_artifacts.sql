CREATE TABLE IF NOT EXISTS context_manifest_artifacts (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  representation_id TEXT NOT NULL,
  manifest_digest TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);

CREATE INDEX IF NOT EXISTS context_manifest_artifacts_by_representation
  ON context_manifest_artifacts(representation_id, id);

CREATE TRIGGER IF NOT EXISTS immutable_context_manifest_artifacts_no_update
  BEFORE UPDATE ON context_manifest_artifacts BEGIN SELECT RAISE(ABORT, 'context_manifest_artifacts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_context_manifest_artifacts_no_delete
  BEFORE DELETE ON context_manifest_artifacts BEGIN SELECT RAISE(ABORT, 'context_manifest_artifacts are immutable'); END;
