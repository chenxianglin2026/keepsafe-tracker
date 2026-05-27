-- ============================================================
-- KeepSafe Database Initialization
-- Create database, user, and schema
-- Run this as a superuser (e.g., postgres) on a fresh PostgreSQL
-- instance with TimescaleDB extension available.
-- ============================================================

-- 1. Create user (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'keepsafe') THEN
        CREATE ROLE keepsafe WITH LOGIN PASSWORD '{{PLACEHOLDER_DB_PASSWORD}}';
    END IF;
END
$$;

-- 2. Create database (if not exists)
SELECT 'CREATE DATABASE keepsafe OWNER keepsafe'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keepsafe')\gexec

-- 3. Connect to the keepsafe database and run the full schema
-- The following lines are meant to be run after \c keepsafe
-- ============================================================
-- Full Schema (run inside keepsafe database)
-- ============================================================

-- 3a. Extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 3b. Devices table
CREATE TABLE IF NOT EXISTS devices (
    device_id       VARCHAR(16) PRIMARY KEY,
    device_token    VARCHAR(64) NOT NULL,
    fw_version      VARCHAR(16),
    first_seen      TIMESTAMPTZ DEFAULT NOW(),
    last_seen       TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE
);

-- 3c. User-Device binding table
CREATE TABLE IF NOT EXISTS user_devices (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL,
    device_id       VARCHAR(16) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    nickname        VARCHAR(64),
    bound_at        TIMESTAMPTZ DEFAULT NOW(),
    is_bound        BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, device_id)
);

CREATE INDEX IF NOT EXISTS idx_user_devices_user_id ON user_devices(user_id);
CREATE INDEX IF NOT EXISTS idx_user_devices_device_id ON user_devices(device_id);

-- 3d. Locations hypertable (TimescaleDB)
CREATE TABLE IF NOT EXISTS locations (
    device_id       VARCHAR(16) NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    lat             DOUBLE PRECISION,
    lng             DOUBLE PRECISION,
    alt             DOUBLE PRECISION,
    speed           DOUBLE PRECISION,
    heading         DOUBLE PRECISION,
    accuracy        DOUBLE PRECISION,
    satellites      INTEGER,
    fix_type        INTEGER,
    cell_id         VARCHAR(32),
    battery         INTEGER,
    charging        BOOLEAN,
    rssi            INTEGER,
    fw_version      VARCHAR(16)
);

SELECT create_hypertable('locations', 'ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_locations_device_id_ts ON locations(device_id, ts DESC);

-- 3e. SOS events table
CREATE TABLE IF NOT EXISTS sos_events (
    id                  SERIAL PRIMARY KEY,
    device_id           VARCHAR(16) NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL,
    lat                 DOUBLE PRECISION,
    lng                 DOUBLE PRECISION,
    accuracy            DOUBLE PRECISION,
    battery             INTEGER,
    trigger_duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sos_events_device_id_ts ON sos_events(device_id, ts DESC);

-- 3f. Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id              SERIAL PRIMARY KEY,
    device_id       VARCHAR(16) NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    alert_type      VARCHAR(32) NOT NULL,
    payload         JSONB
);

CREATE INDEX IF NOT EXISTS idx_alerts_device_id_ts ON alerts(device_id, ts DESC);

-- 3g. Data retention policies
SELECT add_retention_policy('locations', INTERVAL '90 days', if_not_exists => TRUE);

-- 3h. Compression policy (optional, reduces storage)
ALTER TABLE locations SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('locations', INTERVAL '7 days', if_not_exists => TRUE);
