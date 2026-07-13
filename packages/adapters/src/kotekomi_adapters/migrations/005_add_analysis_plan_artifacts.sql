CREATE TABLE IF NOT EXISTS analysis_plan_artifacts (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  representation_id TEXT NOT NULL,
  plan_digest TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);

CREATE INDEX IF NOT EXISTS analysis_plan_artifacts_by_representation
  ON analysis_plan_artifacts(representation_id, id);

CREATE TRIGGER IF NOT EXISTS immutable_analysis_plan_artifacts_no_update
  BEFORE UPDATE ON analysis_plan_artifacts BEGIN SELECT RAISE(ABORT, 'analysis_plan_artifacts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_analysis_plan_artifacts_no_delete
  BEFORE DELETE ON analysis_plan_artifacts BEGIN SELECT RAISE(ABORT, 'analysis_plan_artifacts are immutable'); END;
