PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

-- existing table (keep if you want)
CREATE TABLE IF NOT EXISTS event_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    level TEXT,
    source_service TEXT,
    category TEXT,
    device_code TEXT,
    event_code TEXT,
    message TEXT,
    payload JSON
);

CREATE INDEX IF NOT EXISTS idx_eventlogs_ts ON event_logs(ts);
CREATE INDEX IF NOT EXISTS idx_eventlogs_src ON event_logs(source_service, ts);
CREATE INDEX IF NOT EXISTS idx_eventlogs_level ON event_logs(level, ts);

-- ✅ NEW: canonical logs table for logger_client + log_service
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    service TEXT NOT NULL,
    message TEXT NOT NULL,
    trace_id TEXT,
    extra TEXT
);

CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_service ON logs(service);
