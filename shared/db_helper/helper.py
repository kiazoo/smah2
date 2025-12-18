from .connection import manager

class DBHelper:
    def __init__(self, db_path):
        self.db_path = db_path

    def execute(self, sql, params=None):
        conn = manager.get(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute(sql, params or [])
            conn.commit()
            return cur.rowcount
        except Exception:
            conn.rollback()
            raise

    def fetch_one(self, sql, params=None):
        conn = manager.get(self.db_path)
        cur = conn.cursor()
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return dict(row) if row else None

    def fetch_all(self, sql, params=None):
        conn = manager.get(self.db_path)
        cur = conn.cursor()
        cur.execute(sql, params or [])
        rows = cur.fetchall()
        return [dict(r) for r in rows]
