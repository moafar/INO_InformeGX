-- Stateful report workflow.  This migration only changes the application schema.

CREATE SCHEMA IF NOT EXISTS ergo_app;

ALTER TABLE ergo_app.users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE ergo_app.users
    ADD CONSTRAINT users_role_check
    CHECK (role IN ('AUXILIAR', 'MEDICO', 'COORDINADORA'));

ALTER TABLE ergo_app.report_drafts
    ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'PRELIMINAR',
    ADD COLUMN IF NOT EXISTS medical_owner_user_id BIGINT REFERENCES ergo_app.users(id),
    ADD COLUMN IF NOT EXISTS medical_taken_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 1;

-- Existing drafts predate durable medical ownership.  Their previous clinical
-- phase cannot be inferred safely, so they are conservatively kept out of the
-- auxiliary-editable state.  Drafts created after this migration use the
-- PRELIMINAR default normally.
UPDATE ergo_app.report_drafts
   SET state = 'PRELIMINAR_BLOQUEADO',
       medical_owner_user_id = NULL,
       medical_taken_at = NULL
 WHERE state = 'PRELIMINAR';

ALTER TABLE ergo_app.report_drafts DROP CONSTRAINT IF EXISTS report_drafts_state_check;
ALTER TABLE ergo_app.report_drafts
    ADD CONSTRAINT report_drafts_state_check
    CHECK (state IN ('PRELIMINAR', 'EN_FIRMA', 'PRELIMINAR_BLOQUEADO'));
ALTER TABLE ergo_app.report_drafts DROP CONSTRAINT IF EXISTS report_drafts_medical_ownership_check;
ALTER TABLE ergo_app.report_drafts
    ADD CONSTRAINT report_drafts_medical_ownership_check
    CHECK (
        (state = 'EN_FIRMA' AND medical_owner_user_id IS NOT NULL AND medical_taken_at IS NOT NULL)
        OR
        (state <> 'EN_FIRMA' AND medical_owner_user_id IS NULL AND medical_taken_at IS NULL)
    );

ALTER TABLE ergo_app.report_versions
    ALTER COLUMN filename DROP NOT NULL,
    ALTER COLUMN pdf_sha256 DROP NOT NULL,
    ALTER COLUMN pdf_size_bytes DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'FIRMADO',
    ADD COLUMN IF NOT EXISTS source_version_id UUID REFERENCES ergo_app.report_versions(id),
    ADD COLUMN IF NOT EXISTS signer_signature_profile JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE ergo_app.report_versions DROP CONSTRAINT IF EXISTS report_versions_state_check;
ALTER TABLE ergo_app.report_versions
    ADD CONSTRAINT report_versions_state_check CHECK (state = 'FIRMADO');

CREATE INDEX IF NOT EXISTS report_drafts_state_idx ON ergo_app.report_drafts (state);
CREATE INDEX IF NOT EXISTS report_drafts_medical_owner_idx
    ON ergo_app.report_drafts (medical_owner_user_id) WHERE medical_owner_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS report_versions_source_idx
    ON ergo_app.report_versions (source_version_id) WHERE source_version_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ergo_app.report_workflow_audits (
    id BIGSERIAL PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES ergo_app.studies(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'CREATED', 'MEDICAL_TAKEN', 'MEDICAL_RELEASED', 'MEDICAL_OWNERSHIP_EXPIRED',
        'SIGNED', 'NEW_VERSION_CREATED'
    )),
    actor_user_id BIGINT REFERENCES ergo_app.users(id),
    actor_username TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS report_workflow_audits_study_version_idx
    ON ergo_app.report_workflow_audits (study_id, version_number, occurred_at);

CREATE TABLE IF NOT EXISTS ergo_app.report_pdf_events (
    id BIGSERIAL PRIMARY KEY,
    version_id UUID NOT NULL REFERENCES ergo_app.report_versions(id),
    generated_by_user_id BIGINT NOT NULL REFERENCES ergo_app.users(id),
    generated_by_username TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    filename TEXT NOT NULL,
    pdf_sha256 CHAR(64) NOT NULL CHECK (pdf_sha256 ~ '^[0-9a-f]{64}$'),
    pdf_size_bytes BIGINT NOT NULL CHECK (pdf_size_bytes >= 0)
);

CREATE INDEX IF NOT EXISTS report_pdf_events_version_idx
    ON ergo_app.report_pdf_events (version_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS report_pdf_events_hash_idx
    ON ergo_app.report_pdf_events (pdf_sha256);
