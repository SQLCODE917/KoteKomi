CREATE TABLE IF NOT EXISTS pdf_preflight_reports (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  document_id TEXT NOT NULL,
  raw_blob_id TEXT NOT NULL,
  processing_task_fingerprint_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (raw_blob_id) REFERENCES raw_blobs(id),
  FOREIGN KEY (processing_task_fingerprint_id) REFERENCES processing_task_fingerprints(id)
);

CREATE TABLE IF NOT EXISTS pdf_page_inventories (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  preflight_report_id TEXT NOT NULL,
  page_index INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (preflight_report_id) REFERENCES pdf_preflight_reports(id),
  UNIQUE (preflight_report_id, page_index)
);

CREATE TABLE IF NOT EXISTS pdf_transformation_artifacts (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  preflight_report_id TEXT NOT NULL,
  input_blob_id TEXT NOT NULL,
  output_blob_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (preflight_report_id) REFERENCES pdf_preflight_reports(id),
  FOREIGN KEY (input_blob_id) REFERENCES raw_blobs(id),
  FOREIGN KEY (output_blob_id) REFERENCES raw_blobs(id)
);

CREATE TABLE IF NOT EXISTS pdf_page_extraction_statuses (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  status TEXT,
  review_status TEXT,
  preflight_report_id TEXT NOT NULL,
  page_inventory_id TEXT NOT NULL,
  page_index INTEGER NOT NULL,
  representation_id TEXT,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (preflight_report_id) REFERENCES pdf_preflight_reports(id),
  FOREIGN KEY (page_inventory_id) REFERENCES pdf_page_inventories(id),
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  UNIQUE (preflight_report_id, page_index)
);

CREATE INDEX IF NOT EXISTS idx_pdf_preflight_reports_task
ON pdf_preflight_reports(processing_task_fingerprint_id);
CREATE INDEX IF NOT EXISTS idx_pdf_preflight_reports_document
ON pdf_preflight_reports(document_id);
CREATE INDEX IF NOT EXISTS idx_pdf_page_inventories_report
ON pdf_page_inventories(preflight_report_id, page_index);
CREATE INDEX IF NOT EXISTS idx_pdf_page_extraction_statuses_report
ON pdf_page_extraction_statuses(preflight_report_id, page_index);
CREATE INDEX IF NOT EXISTS idx_pdf_transformation_artifacts_report
ON pdf_transformation_artifacts(preflight_report_id);

CREATE TRIGGER IF NOT EXISTS immutable_pdf_preflight_reports_no_update
BEFORE UPDATE ON pdf_preflight_reports BEGIN
  SELECT RAISE(ABORT, 'pdf_preflight_reports are immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_preflight_reports_no_delete
BEFORE DELETE ON pdf_preflight_reports BEGIN
  SELECT RAISE(ABORT, 'pdf_preflight_reports are immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_page_inventories_no_update
BEFORE UPDATE ON pdf_page_inventories BEGIN
  SELECT RAISE(ABORT, 'pdf_page_inventories are immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_page_inventories_no_delete
BEFORE DELETE ON pdf_page_inventories BEGIN
  SELECT RAISE(ABORT, 'pdf_page_inventories are immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_page_extraction_statuses_no_update
BEFORE UPDATE ON pdf_page_extraction_statuses BEGIN
  SELECT RAISE(ABORT, 'pdf_page_extraction_statuses are immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_page_extraction_statuses_no_delete
BEFORE DELETE ON pdf_page_extraction_statuses BEGIN
  SELECT RAISE(ABORT, 'pdf_page_extraction_statuses are immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_transformation_artifacts_no_update
BEFORE UPDATE ON pdf_transformation_artifacts BEGIN
  SELECT RAISE(ABORT, 'pdf_transformation_artifacts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_transformation_artifacts_no_delete
BEFORE DELETE ON pdf_transformation_artifacts BEGIN
  SELECT RAISE(ABORT, 'pdf_transformation_artifacts are immutable');
END;
