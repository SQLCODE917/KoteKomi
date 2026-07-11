CREATE TRIGGER IF NOT EXISTS immutable_raw_blobs_no_update
BEFORE UPDATE ON raw_blobs BEGIN SELECT RAISE(ABORT, 'raw_blobs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_captures_no_update
BEFORE UPDATE ON source_captures BEGIN SELECT RAISE(ABORT, 'source_captures are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_documents_no_update
BEFORE UPDATE ON documents BEGIN SELECT RAISE(ABORT, 'documents are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_representations_no_update
BEFORE UPDATE ON document_representations BEGIN SELECT RAISE(ABORT, 'document_representations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_text_views_no_update
BEFORE UPDATE ON text_views BEGIN SELECT RAISE(ABORT, 'text_views are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_nodes_no_update
BEFORE UPDATE ON document_nodes BEGIN SELECT RAISE(ABORT, 'document_nodes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_edges_no_update
BEFORE UPDATE ON document_edges BEGIN SELECT RAISE(ABORT, 'document_edges are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_regions_no_update
BEFORE UPDATE ON source_regions BEGIN SELECT RAISE(ABORT, 'source_regions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_parse_quality_reports_no_update
BEFORE UPDATE ON parse_quality_reports BEGIN SELECT RAISE(ABORT, 'parse_quality_reports are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_revision_relations_no_update
BEFORE UPDATE ON document_revision_relations BEGIN SELECT RAISE(ABORT, 'document_revision_relations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_assertion_evidence_links_no_update
BEFORE UPDATE ON assertion_evidence_links BEGIN SELECT RAISE(ABORT, 'assertion_evidence_links are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_reanchoring_relations_no_update
BEFORE UPDATE ON evidence_reanchoring_relations BEGIN SELECT RAISE(ABORT, 'evidence_reanchoring_relations are immutable'); END;
