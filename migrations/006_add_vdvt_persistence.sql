-- Preserve the two clinical VD/VT alternatives and selected source for durable drafts.
-- Signed versions store the same metadata inside their existing immutable snapshot.
-- NULL is intentional for drafts created before this migration: their alternative
-- source values cannot be recovered without re-reading clinical staging.

ALTER TABLE ergo_app.report_drafts
    ADD COLUMN IF NOT EXISTS vdvt_metadata JSONB;

COMMENT ON COLUMN ergo_app.report_drafts.vdvt_metadata IS
    'VD/VT measured and estimated values plus selected_source; NULL means unavailable in a legacy draft.';
