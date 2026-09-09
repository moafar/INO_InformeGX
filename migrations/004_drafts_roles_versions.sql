-- Persistent application workflow. This migration never touches clinical staging.

CREATE SCHEMA IF NOT EXISTS ergo_app;

ALTER TABLE ergo_app.users
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'MEDICO'
    CHECK (role IN ('AUXILIAR', 'MEDICO'));

CREATE TABLE IF NOT EXISTS ergo_app.studies (
    id UUID PRIMARY KEY,
    gx_source TEXT NOT NULL DEFAULT 'GXPostgresDataSource',
    lookup_patient_id_num TEXT NOT NULL,
    lookup_visit_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ergo_app.report_drafts (
    id UUID PRIMARY KEY,
    study_id UUID NOT NULL UNIQUE REFERENCES ergo_app.studies(id) ON DELETE CASCADE,
    next_version_number INTEGER NOT NULL DEFAULT 1 CHECK (next_version_number > 0),
    created_from_version_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ergo_app.draft_values (
    draft_id UUID NOT NULL REFERENCES ergo_app.report_drafts(id) ON DELETE CASCADE,
    field_key TEXT NOT NULL,
    variable_type TEXT NOT NULL CHECK (variable_type IN ('DIRECTO', 'CALCULADO', 'MANUAL', 'INTERPRETACIÓN')),
    original_value TEXT NOT NULL DEFAULT '',
    current_value TEXT NOT NULL DEFAULT '',
    edited BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (draft_id, field_key)
);

CREATE TABLE IF NOT EXISTS ergo_app.draft_locks (
    draft_id UUID PRIMARY KEY REFERENCES ergo_app.report_drafts(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES ergo_app.users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS draft_locks_expiry_idx ON ergo_app.draft_locks (expires_at);

CREATE TABLE IF NOT EXISTS ergo_app.report_versions (
    id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES ergo_app.studies(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    signed_by_user_id BIGINT NOT NULL REFERENCES ergo_app.users(id),
    signed_by_username TEXT NOT NULL,
    signed_at TIMESTAMPTZ NOT NULL,
    filename TEXT NOT NULL,
    pdf_sha256 CHAR(64) NOT NULL CHECK (pdf_sha256 ~ '^[0-9a-f]{64}$'),
    pdf_size_bytes BIGINT NOT NULL CHECK (pdf_size_bytes >= 0),
    study_identity JSONB NOT NULL,
    snapshot JSONB NOT NULL,
    UNIQUE (study_id, version_number)
);

CREATE INDEX IF NOT EXISTS report_versions_study_idx
    ON ergo_app.report_versions (study_id, version_number DESC);
