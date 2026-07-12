CREATE TABLE IF NOT EXISTS extraction_tasks (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  context_manifest_id TEXT NOT NULL,
  task_fingerprint TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_runs (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  review_status TEXT,
  extraction_task_id TEXT NOT NULL,
  task_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (extraction_task_id) REFERENCES extraction_tasks(id)
);

CREATE INDEX IF NOT EXISTS model_runs_by_task
  ON model_runs(extraction_task_id, started_at, id);

CREATE INDEX IF NOT EXISTS model_runs_by_fingerprint
  ON model_runs(task_fingerprint, started_at, id);

CREATE TRIGGER IF NOT EXISTS immutable_extraction_tasks_no_update
  BEFORE UPDATE ON extraction_tasks BEGIN SELECT RAISE(ABORT, 'extraction_tasks are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_extraction_tasks_no_delete
  BEFORE DELETE ON extraction_tasks BEGIN SELECT RAISE(ABORT, 'extraction_tasks are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_model_runs_no_update
  BEFORE UPDATE ON model_runs BEGIN SELECT RAISE(ABORT, 'model_runs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_model_runs_no_delete
  BEFORE DELETE ON model_runs BEGIN SELECT RAISE(ABORT, 'model_runs are immutable'); END;
