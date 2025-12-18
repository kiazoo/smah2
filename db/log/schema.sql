PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

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
