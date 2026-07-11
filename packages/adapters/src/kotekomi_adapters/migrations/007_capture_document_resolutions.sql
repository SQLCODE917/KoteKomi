CREATE TABLE IF NOT EXISTS capture_document_resolutions (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS immutable_capture_document_resolutions_no_update
BEFORE UPDATE ON capture_document_resolutions
BEGIN SELECT RAISE(ABORT, 'capture_document_resolutions are immutable'); END;

CREATE TRIGGER IF NOT EXISTS immutable_capture_document_resolutions_no_delete
BEFORE DELETE ON capture_document_resolutions
BEGIN SELECT RAISE(ABORT, 'capture_document_resolutions are immutable'); END;
