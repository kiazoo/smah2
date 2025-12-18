PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    status TEXT DEFAULT 'inactive',
    version TEXT,
    config JSON,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    port TEXT,
    baudrate INTEGER,
    params JSON,
    assigned_service TEXT,
    enabled INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS routing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    producer TEXT,
    consumer TEXT,
    direction TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS platform_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_name TEXT NOT NULL,
    protocol TEXT,
    endpoint TEXT,
    token TEXT,
    enabled INTEGER DEFAULT 1,
    config JSON
);

CREATE TABLE IF NOT EXISTS config_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    scope_key TEXT,
    key TEXT NOT NULL,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
