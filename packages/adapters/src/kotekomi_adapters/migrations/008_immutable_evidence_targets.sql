CREATE TABLE IF NOT EXISTS evidence_targets (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_validation_attempts (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS immutable_evidence_targets_no_update
BEFORE UPDATE ON evidence_targets
BEGIN SELECT RAISE(ABORT, 'evidence_targets are immutable'); END;

CREATE TRIGGER IF NOT EXISTS immutable_evidence_targets_no_delete
BEFORE DELETE ON evidence_targets
BEGIN SELECT RAISE(ABORT, 'evidence_targets are immutable'); END;

CREATE TRIGGER IF NOT EXISTS immutable_evidence_validation_attempts_no_update
BEFORE UPDATE ON evidence_validation_attempts
BEGIN SELECT RAISE(ABORT, 'evidence_validation_attempts are immutable'); END;

CREATE TRIGGER IF NOT EXISTS immutable_evidence_validation_attempts_no_delete
BEFORE DELETE ON evidence_validation_attempts
BEGIN SELECT RAISE(ABORT, 'evidence_validation_attempts are immutable'); END;
