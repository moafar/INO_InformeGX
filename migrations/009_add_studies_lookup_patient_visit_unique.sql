-- Prevent duplicate application studies for the same patient visit.
-- This migration only changes the application schema.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'ergo_app.studies'::regclass
           AND conname = 'studies_lookup_patient_visit_unique'
    ) THEN
        ALTER TABLE ergo_app.studies
            ADD CONSTRAINT studies_lookup_patient_visit_unique
            UNIQUE (lookup_patient_id_num, lookup_visit_datetime);
    END IF;
END
$$;
