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
  source_id TEXT NOT NULL, provider_version TEXT,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES sources(id)
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
  source_id TEXT NOT NULL, blob_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES sources(id), FOREIGN KEY (blob_id) REFERENCES raw_blobs(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_captures_idempotency ON source_captures(id);
CREATE TABLE IF NOT EXISTS capture_document_resolutions (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  capture_id TEXT NOT NULL, document_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (capture_id) REFERENCES source_captures(id), FOREIGN KEY (document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS document_revision_relations (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  earlier_document_id TEXT NOT NULL, later_document_id TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source_provider_version
  ON documents(source_id, provider_version) WHERE provider_version IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_document_revision_relations_earlier
  ON document_revision_relations(earlier_document_id);
CREATE TABLE IF NOT EXISTS document_representations (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  document_id TEXT NOT NULL, processing_task_fingerprint_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (processing_task_fingerprint_id) REFERENCES processing_task_fingerprints(id)
);
CREATE TABLE IF NOT EXISTS text_views (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);
CREATE TABLE IF NOT EXISTS document_nodes (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, parent_node_id TEXT, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (parent_node_id) REFERENCES document_nodes(id)
);
CREATE TABLE IF NOT EXISTS document_edges (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);
CREATE TABLE IF NOT EXISTS source_regions (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);
CREATE TABLE IF NOT EXISTS document_tables (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);
CREATE TABLE IF NOT EXISTS document_table_fragments (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, table_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (table_id) REFERENCES document_tables(id)
);
CREATE TABLE IF NOT EXISTS document_table_rows (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, table_id TEXT NOT NULL,
  fragment_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (table_id) REFERENCES document_tables(id),
  FOREIGN KEY (fragment_id) REFERENCES document_table_fragments(id)
);
CREATE TABLE IF NOT EXISTS document_table_cells (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, table_id TEXT NOT NULL,
  fragment_id TEXT NOT NULL, row_id TEXT NOT NULL, node_id TEXT, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (table_id) REFERENCES document_tables(id),
  FOREIGN KEY (fragment_id) REFERENCES document_table_fragments(id),
  FOREIGN KEY (row_id) REFERENCES document_table_rows(id),
  FOREIGN KEY (node_id) REFERENCES document_nodes(id)
);
CREATE TABLE IF NOT EXISTS document_table_annotations (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, table_id TEXT NOT NULL,
  fragment_id TEXT, node_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (table_id) REFERENCES document_tables(id),
  FOREIGN KEY (fragment_id) REFERENCES document_table_fragments(id),
  FOREIGN KEY (node_id) REFERENCES document_nodes(id)
);
CREATE TABLE IF NOT EXISTS document_references (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL,
  marker_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (marker_node_id) REFERENCES document_nodes(id),
  FOREIGN KEY (target_node_id) REFERENCES document_nodes(id)
);
CREATE TABLE IF NOT EXISTS parse_quality_reports (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id)
);
CREATE INDEX IF NOT EXISTS idx_document_representations_document_id ON document_representations(document_id);
CREATE INDEX IF NOT EXISTS idx_text_views_representation_id ON text_views(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_nodes_representation_id ON document_nodes(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_edges_representation_id ON document_edges(representation_id);
CREATE INDEX IF NOT EXISTS idx_source_regions_representation_id ON source_regions(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_tables_representation_id ON document_tables(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_table_fragments_representation_id ON document_table_fragments(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_table_rows_representation_id ON document_table_rows(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_table_cells_representation_id ON document_table_cells(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_table_annotations_representation_id ON document_table_annotations(representation_id);
CREATE INDEX IF NOT EXISTS idx_document_references_representation_id ON document_references(representation_id);
CREATE INDEX IF NOT EXISTS idx_parse_quality_reports_representation_id ON parse_quality_reports(representation_id);
CREATE TABLE IF NOT EXISTS assertion_evidence_links (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_validation_attempts (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processing_task_fingerprints (
  id TEXT PRIMARY KEY,
  task_kind TEXT NOT NULL,
  document_id TEXT NOT NULL,
  blob_id TEXT NOT NULL,
  fingerprint_digest TEXT NOT NULL UNIQUE,
  build_identity_digest TEXT NOT NULL,
  processor_name TEXT NOT NULL,
  processor_version TEXT NOT NULL,
  processor_config_digest TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (blob_id) REFERENCES raw_blobs(id)
);
CREATE TABLE IF NOT EXISTS processing_attempts (
  id TEXT PRIMARY KEY,
  task_fingerprint_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (task_fingerprint_id) REFERENCES processing_task_fingerprints(id)
);
CREATE TABLE IF NOT EXISTS processing_attempt_outcomes (
  id TEXT PRIMARY KEY,
  attempt_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (attempt_id) REFERENCES processing_attempts(id)
);
CREATE INDEX IF NOT EXISTS processing_attempts_by_fingerprint
ON processing_attempts(task_fingerprint_id, started_at, id);
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
CREATE TRIGGER IF NOT EXISTS immutable_document_tables_no_update BEFORE UPDATE ON document_tables BEGIN SELECT RAISE(ABORT, 'document_tables are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_fragments_no_update BEFORE UPDATE ON document_table_fragments BEGIN SELECT RAISE(ABORT, 'document_table_fragments are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_rows_no_update BEFORE UPDATE ON document_table_rows BEGIN SELECT RAISE(ABORT, 'document_table_rows are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_cells_no_update BEFORE UPDATE ON document_table_cells BEGIN SELECT RAISE(ABORT, 'document_table_cells are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_annotations_no_update BEFORE UPDATE ON document_table_annotations BEGIN SELECT RAISE(ABORT, 'document_table_annotations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_references_no_update BEFORE UPDATE ON document_references BEGIN SELECT RAISE(ABORT, 'document_references are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_parse_quality_reports_no_update BEFORE UPDATE ON parse_quality_reports BEGIN SELECT RAISE(ABORT, 'parse_quality_reports are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_provenance_activities_no_update BEFORE UPDATE ON provenance_activities BEGIN SELECT RAISE(ABORT, 'provenance_activities are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_targets_no_update BEFORE UPDATE ON evidence_targets BEGIN SELECT RAISE(ABORT, 'evidence_targets are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_validation_attempts_no_update BEFORE UPDATE ON evidence_validation_attempts BEGIN SELECT RAISE(ABORT, 'evidence_validation_attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_processing_task_fingerprints_no_update BEFORE UPDATE ON processing_task_fingerprints BEGIN SELECT RAISE(ABORT, 'processing_task_fingerprints are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_processing_attempts_no_update BEFORE UPDATE ON processing_attempts BEGIN SELECT RAISE(ABORT, 'processing_attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_processing_attempt_outcomes_no_update BEFORE UPDATE ON processing_attempt_outcomes BEGIN SELECT RAISE(ABORT, 'processing_attempt_outcomes are immutable'); END;
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
CREATE TRIGGER IF NOT EXISTS immutable_document_tables_no_delete BEFORE DELETE ON document_tables BEGIN SELECT RAISE(ABORT, 'document_tables are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_fragments_no_delete BEFORE DELETE ON document_table_fragments BEGIN SELECT RAISE(ABORT, 'document_table_fragments are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_rows_no_delete BEFORE DELETE ON document_table_rows BEGIN SELECT RAISE(ABORT, 'document_table_rows are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_cells_no_delete BEFORE DELETE ON document_table_cells BEGIN SELECT RAISE(ABORT, 'document_table_cells are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_table_annotations_no_delete BEFORE DELETE ON document_table_annotations BEGIN SELECT RAISE(ABORT, 'document_table_annotations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_references_no_delete BEFORE DELETE ON document_references BEGIN SELECT RAISE(ABORT, 'document_references are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_parse_quality_reports_no_delete BEFORE DELETE ON parse_quality_reports BEGIN SELECT RAISE(ABORT, 'parse_quality_reports are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_provenance_activities_no_delete BEFORE DELETE ON provenance_activities BEGIN SELECT RAISE(ABORT, 'provenance_activities are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_targets_no_delete BEFORE DELETE ON evidence_targets BEGIN SELECT RAISE(ABORT, 'evidence_targets are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_validation_attempts_no_delete BEFORE DELETE ON evidence_validation_attempts BEGIN SELECT RAISE(ABORT, 'evidence_validation_attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_processing_task_fingerprints_no_delete BEFORE DELETE ON processing_task_fingerprints BEGIN SELECT RAISE(ABORT, 'processing_task_fingerprints are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_processing_attempts_no_delete BEFORE DELETE ON processing_attempts BEGIN SELECT RAISE(ABORT, 'processing_attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_processing_attempt_outcomes_no_delete BEFORE DELETE ON processing_attempt_outcomes BEGIN SELECT RAISE(ABORT, 'processing_attempt_outcomes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_assertion_evidence_links_no_delete BEFORE DELETE ON assertion_evidence_links BEGIN SELECT RAISE(ABORT, 'assertion_evidence_links are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_reanchoring_relations_no_delete BEFORE DELETE ON evidence_reanchoring_relations BEGIN SELECT RAISE(ABORT, 'evidence_reanchoring_relations are immutable'); END;
