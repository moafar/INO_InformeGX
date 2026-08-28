-- Manual migration only. Do not auto-run or seed users.

CREATE SCHEMA IF NOT EXISTS ergo_app;

CREATE TABLE IF NOT EXISTS ergo_app.users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
