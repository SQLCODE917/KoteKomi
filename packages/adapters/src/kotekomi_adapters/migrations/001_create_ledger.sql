CREATE TABLE IF NOT EXISTS ledger_migrations (
  version TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actors (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS places (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_targets (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assertions (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assertions_status ON assertions(status);

CREATE TABLE IF NOT EXISTS relationships (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS argument_edges (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provenance_activities (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposed_changes (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proposed_changes_review_status
  ON proposed_changes(review_status);

CREATE TABLE IF NOT EXISTS briefings (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_blobs (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_captures (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_captures_idempotency ON source_captures(id);
CREATE TABLE IF NOT EXISTS capture_document_resolutions (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_revision_relations (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_representations (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS text_views (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_nodes (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_edges (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_regions (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parse_quality_reports (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assertion_evidence_links (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_validation_attempts (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_reanchoring_relations (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS immutable_raw_blobs_no_update BEFORE UPDATE ON raw_blobs BEGIN SELECT RAISE(ABORT, 'raw_blobs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_captures_no_update BEFORE UPDATE ON source_captures BEGIN SELECT RAISE(ABORT, 'source_captures are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_capture_document_resolutions_no_update BEFORE UPDATE ON capture_document_resolutions BEGIN SELECT RAISE(ABORT, 'capture_document_resolutions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_documents_no_update BEFORE UPDATE ON documents BEGIN SELECT RAISE(ABORT, 'documents are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_revision_relations_no_update BEFORE UPDATE ON document_revision_relations BEGIN SELECT RAISE(ABORT, 'document_revision_relations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_representations_no_update BEFORE UPDATE ON document_representations BEGIN SELECT RAISE(ABORT, 'document_representations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_text_views_no_update BEFORE UPDATE ON text_views BEGIN SELECT RAISE(ABORT, 'text_views are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_nodes_no_update BEFORE UPDATE ON document_nodes BEGIN SELECT RAISE(ABORT, 'document_nodes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_edges_no_update BEFORE UPDATE ON document_edges BEGIN SELECT RAISE(ABORT, 'document_edges are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_regions_no_update BEFORE UPDATE ON source_regions BEGIN SELECT RAISE(ABORT, 'source_regions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_parse_quality_reports_no_update BEFORE UPDATE ON parse_quality_reports BEGIN SELECT RAISE(ABORT, 'parse_quality_reports are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_targets_no_update BEFORE UPDATE ON evidence_targets BEGIN SELECT RAISE(ABORT, 'evidence_targets are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_validation_attempts_no_update BEFORE UPDATE ON evidence_validation_attempts BEGIN SELECT RAISE(ABORT, 'evidence_validation_attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_assertion_evidence_links_no_update BEFORE UPDATE ON assertion_evidence_links BEGIN SELECT RAISE(ABORT, 'assertion_evidence_links are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_reanchoring_relations_no_update BEFORE UPDATE ON evidence_reanchoring_relations BEGIN SELECT RAISE(ABORT, 'evidence_reanchoring_relations are immutable'); END;

CREATE TRIGGER IF NOT EXISTS immutable_raw_blobs_no_delete BEFORE DELETE ON raw_blobs BEGIN SELECT RAISE(ABORT, 'raw_blobs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_captures_no_delete BEFORE DELETE ON source_captures BEGIN SELECT RAISE(ABORT, 'source_captures are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_capture_document_resolutions_no_delete BEFORE DELETE ON capture_document_resolutions BEGIN SELECT RAISE(ABORT, 'capture_document_resolutions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_documents_no_delete BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT, 'documents are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_revision_relations_no_delete BEFORE DELETE ON document_revision_relations BEGIN SELECT RAISE(ABORT, 'document_revision_relations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_representations_no_delete BEFORE DELETE ON document_representations BEGIN SELECT RAISE(ABORT, 'document_representations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_text_views_no_delete BEFORE DELETE ON text_views BEGIN SELECT RAISE(ABORT, 'text_views are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_nodes_no_delete BEFORE DELETE ON document_nodes BEGIN SELECT RAISE(ABORT, 'document_nodes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_edges_no_delete BEFORE DELETE ON document_edges BEGIN SELECT RAISE(ABORT, 'document_edges are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_regions_no_delete BEFORE DELETE ON source_regions BEGIN SELECT RAISE(ABORT, 'source_regions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_parse_quality_reports_no_delete BEFORE DELETE ON parse_quality_reports BEGIN SELECT RAISE(ABORT, 'parse_quality_reports are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_targets_no_delete BEFORE DELETE ON evidence_targets BEGIN SELECT RAISE(ABORT, 'evidence_targets are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_validation_attempts_no_delete BEFORE DELETE ON evidence_validation_attempts BEGIN SELECT RAISE(ABORT, 'evidence_validation_attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_assertion_evidence_links_no_delete BEFORE DELETE ON assertion_evidence_links BEGIN SELECT RAISE(ABORT, 'assertion_evidence_links are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_reanchoring_relations_no_delete BEFORE DELETE ON evidence_reanchoring_relations BEGIN SELECT RAISE(ABORT, 'evidence_reanchoring_relations are immutable'); END;
