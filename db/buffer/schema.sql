PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS uplink_buffer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    uplink_name TEXT NOT NULL,
    payload TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_uplink_buffer_name
ON uplink_buffer(uplink_name);

CREATE INDEX IF NOT EXISTS idx_uplink_buffer_ts
ON uplink_buffer(timestamp);
