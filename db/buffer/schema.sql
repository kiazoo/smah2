PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS telemetry_buffer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    platform_name TEXT NOT NULL,
    target_endpoint TEXT,
    payload JSON NOT NULL,
    content_type TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_buffer_status_time ON telemetry_buffer(status, created_at);
CREATE INDEX IF NOT EXISTS idx_buffer_next_retry ON telemetry_buffer(status, next_retry_at);
