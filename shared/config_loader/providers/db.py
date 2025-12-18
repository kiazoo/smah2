import sqlite3
from pathlib import Path

DEFAULT_DB = "db/config/config.db"

def load_from_db(db_path=DEFAULT_DB):
    result = {}

    if not Path(db_path).exists():
        return result

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        cur.execute("SELECT key, value FROM config")
        for k, v in cur.fetchall():
            result[k] = v
    except Exception:
        pass
    finally:
        conn.close()

    return result
