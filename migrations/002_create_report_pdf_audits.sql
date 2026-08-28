-- Manual migration only. Do not run automatically from the application.
-- This table belongs to the authentication database, not the clinical source.

CREATE SCHEMA IF NOT EXISTS ergo_app;

CREATE TABLE IF NOT EXISTS ergo_app.report_pdf_audits (
    id BIGSERIAL PRIMARY KEY,
    patient_id_num TEXT NOT NULL,
    visit_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    generated_by_user_id BIGINT NOT NULL REFERENCES ergo_app.users (id),
    generated_by_username TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    filename TEXT NOT NULL,
    pdf_sha256 CHAR(64) NOT NULL CHECK (pdf_sha256 ~ '^[0-9a-f]{64}$'),
    pdf_size_bytes BIGINT NOT NULL CHECK (pdf_size_bytes >= 0)
);

CREATE INDEX IF NOT EXISTS report_pdf_audits_study_idx
    ON ergo_app.report_pdf_audits (patient_id_num, visit_datetime);

CREATE INDEX IF NOT EXISTS report_pdf_audits_user_idx
    ON ergo_app.report_pdf_audits (generated_by_user_id, generated_at DESC);

CREATE INDEX IF NOT EXISTS report_pdf_audits_hash_idx
    ON ergo_app.report_pdf_audits (pdf_sha256);
