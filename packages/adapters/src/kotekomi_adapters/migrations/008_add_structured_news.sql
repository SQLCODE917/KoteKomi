CREATE TABLE IF NOT EXISTS document_source_selectors (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, node_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (node_id) REFERENCES document_nodes(id),
  UNIQUE (representation_id, node_id)
);

CREATE TABLE IF NOT EXISTS news_rights_profiles (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  provider_namespace TEXT NOT NULL, policy_id TEXT NOT NULL, payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_delivery_envelope_artifacts (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  capture_id TEXT NOT NULL, blob_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY (capture_id) REFERENCES source_captures(id),
  FOREIGN KEY (blob_id) REFERENCES raw_blobs(id),
  UNIQUE (capture_id)
);

CREATE TABLE IF NOT EXISTS news_revision_classifications (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  document_id TEXT NOT NULL, source_id TEXT NOT NULL, provider_namespace TEXT NOT NULL,
  provider_item_id TEXT NOT NULL, provider_version TEXT NOT NULL,
  normalized_version_key TEXT NOT NULL, rights_profile_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (source_id) REFERENCES sources(id),
  FOREIGN KEY (rights_profile_id) REFERENCES news_rights_profiles(id),
  UNIQUE (provider_namespace, provider_item_id, provider_version)
);

CREATE TABLE IF NOT EXISTS news_representation_metadata (
  id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, review_status TEXT,
  representation_id TEXT NOT NULL, document_id TEXT NOT NULL,
  revision_classification_id TEXT NOT NULL, rights_profile_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY (representation_id) REFERENCES document_representations(id),
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (revision_classification_id) REFERENCES news_revision_classifications(id),
  FOREIGN KEY (rights_profile_id) REFERENCES news_rights_profiles(id),
  UNIQUE (representation_id)
);

CREATE INDEX IF NOT EXISTS idx_document_source_selectors_representation
  ON document_source_selectors(representation_id, node_id);
CREATE INDEX IF NOT EXISTS idx_news_revision_provider_identity
  ON news_revision_classifications(provider_namespace, provider_item_id, provider_version);
CREATE INDEX IF NOT EXISTS idx_news_revision_source_version
  ON news_revision_classifications(source_id, normalized_version_key, id);
CREATE INDEX IF NOT EXISTS idx_news_representation_document
  ON news_representation_metadata(document_id, representation_id);

CREATE TRIGGER IF NOT EXISTS immutable_document_source_selectors_no_update BEFORE UPDATE ON document_source_selectors BEGIN SELECT RAISE(ABORT, 'document_source_selectors are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_document_source_selectors_no_delete BEFORE DELETE ON document_source_selectors BEGIN SELECT RAISE(ABORT, 'document_source_selectors are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_rights_profiles_no_update BEFORE UPDATE ON news_rights_profiles BEGIN SELECT RAISE(ABORT, 'news_rights_profiles are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_rights_profiles_no_delete BEFORE DELETE ON news_rights_profiles BEGIN SELECT RAISE(ABORT, 'news_rights_profiles are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_delivery_envelope_artifacts_no_update BEFORE UPDATE ON news_delivery_envelope_artifacts BEGIN SELECT RAISE(ABORT, 'news_delivery_envelope_artifacts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_delivery_envelope_artifacts_no_delete BEFORE DELETE ON news_delivery_envelope_artifacts BEGIN SELECT RAISE(ABORT, 'news_delivery_envelope_artifacts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_revision_classifications_no_update BEFORE UPDATE ON news_revision_classifications BEGIN SELECT RAISE(ABORT, 'news_revision_classifications are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_revision_classifications_no_delete BEFORE DELETE ON news_revision_classifications BEGIN SELECT RAISE(ABORT, 'news_revision_classifications are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_representation_metadata_no_update BEFORE UPDATE ON news_representation_metadata BEGIN SELECT RAISE(ABORT, 'news_representation_metadata are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_news_representation_metadata_no_delete BEFORE DELETE ON news_representation_metadata BEGIN SELECT RAISE(ABORT, 'news_representation_metadata are immutable'); END;
