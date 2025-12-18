import sqlite3
import threading
from pathlib import Path

class SQLiteConnectionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._connections = {}

    def get(self, db_path):
        with self._lock:
            if db_path not in self._connections:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                self._connections[db_path] = conn
            return self._connections[db_path]

manager = SQLiteConnectionManager()
