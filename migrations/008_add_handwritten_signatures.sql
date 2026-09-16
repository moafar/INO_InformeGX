-- Handwritten PNG signatures for medical profiles and immutable signed versions.
-- This migration only changes the application schema.

ALTER TABLE ergo_app.user_signature_profiles
    ADD COLUMN IF NOT EXISTS signature_image BYTEA,
    ADD COLUMN IF NOT EXISTS signature_image_mime_type TEXT,
    ADD COLUMN IF NOT EXISTS signature_image_updated_at TIMESTAMPTZ;

ALTER TABLE ergo_app.user_signature_profiles
    DROP CONSTRAINT IF EXISTS user_signature_profiles_signature_image_check;
ALTER TABLE ergo_app.user_signature_profiles
    ADD CONSTRAINT user_signature_profiles_signature_image_check CHECK (
        (signature_image IS NULL AND signature_image_mime_type IS NULL AND signature_image_updated_at IS NULL)
        OR
        (signature_image IS NOT NULL
         AND signature_image_mime_type = 'image/png'
         AND signature_image_updated_at IS NOT NULL
         AND OCTET_LENGTH(signature_image) BETWEEN 1 AND 1048576)
    );

ALTER TABLE ergo_app.report_versions
    ADD COLUMN IF NOT EXISTS signer_signature_image BYTEA,
    ADD COLUMN IF NOT EXISTS signer_signature_image_mime_type TEXT,
    ADD COLUMN IF NOT EXISTS signer_signature_image_updated_at TIMESTAMPTZ;

ALTER TABLE ergo_app.report_versions
    DROP CONSTRAINT IF EXISTS report_versions_signature_image_check;
ALTER TABLE ergo_app.report_versions
    ADD CONSTRAINT report_versions_signature_image_check CHECK (
        (signer_signature_image IS NULL
         AND signer_signature_image_mime_type IS NULL
         AND signer_signature_image_updated_at IS NULL)
        OR
        (signer_signature_image IS NOT NULL
         AND signer_signature_image_mime_type = 'image/png'
         AND signer_signature_image_updated_at IS NOT NULL
         AND OCTET_LENGTH(signer_signature_image) BETWEEN 1 AND 1048576)
    );

CREATE TABLE IF NOT EXISTS ergo_app.user_signature_profile_audits (
    id BIGSERIAL PRIMARY KEY,
    profile_user_id BIGINT NOT NULL REFERENCES ergo_app.users(id),
    actor_user_id BIGINT NOT NULL REFERENCES ergo_app.users(id),
    actor_username TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type = 'SIGNATURE_IMAGE_UPDATED'),
    occurred_at TIMESTAMPTZ NOT NULL,
    image_mime_type TEXT NOT NULL CHECK (image_mime_type = 'image/png'),
    image_sha256 CHAR(64) NOT NULL CHECK (image_sha256 ~ '^[0-9a-f]{64}$'),
    image_size_bytes BIGINT NOT NULL CHECK (image_size_bytes BETWEEN 1 AND 1048576)
);

CREATE INDEX IF NOT EXISTS user_signature_profile_audits_user_idx
    ON ergo_app.user_signature_profile_audits (profile_user_id, occurred_at DESC);
