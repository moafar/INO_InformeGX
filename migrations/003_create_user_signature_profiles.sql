-- Manual migration only. Apply to the authentication database.
-- No signature image is stored; the profile is textual and belongs to one user.

CREATE SCHEMA IF NOT EXISTS ergo_app;

CREATE TABLE IF NOT EXISTS ergo_app.user_signature_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES ergo_app.users (id) ON DELETE CASCADE,
    signature_name TEXT NOT NULL CHECK (BTRIM(signature_name) <> ''),
    profession_specialty TEXT NOT NULL CHECK (BTRIM(profession_specialty) <> ''),
    professional_registration TEXT NOT NULL CHECK (BTRIM(professional_registration) <> ''),
    institutional_line TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
