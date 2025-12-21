import json
from datetime import datetime
from shared.db_helper import db_buffer

class BufferStore:
    def __init__(self, max_records: int = 1000):
        self.max_records = max_records

    def enqueue(self, uplink_name: str, payload: dict):
        ts = datetime.utcnow().isoformat() + "Z"
        db_buffer.execute(
            """
            INSERT INTO uplink_buffer(timestamp, uplink_name, payload, retry_count)
            VALUES (?, ?, ?, 0)
            """,
            (ts, uplink_name, json.dumps(payload, ensure_ascii=False)),
        )

        # FIFO keep last max_records
        db_buffer.execute(
            f"""
            DELETE FROM uplink_buffer
            WHERE id NOT IN (
                SELECT id FROM uplink_buffer
                ORDER BY id DESC
                LIMIT {int(self.max_records)}
            )
            """
        )

    def fetch_batch(self, uplink_name: str, limit: int = 50):
        return db_buffer.fetch_all(
            """
            SELECT id, timestamp, payload, retry_count
            FROM uplink_buffer
            WHERE uplink_name = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (uplink_name, int(limit)),
        )

    def mark_sent(self, row_id: int):
        db_buffer.execute("DELETE FROM uplink_buffer WHERE id = ?", (row_id,))

    def inc_retry(self, row_id: int):
        db_buffer.execute(
            "UPDATE uplink_buffer SET retry_count = retry_count + 1 WHERE id = ?",
            (row_id,),
        )

    def count(self, uplink_name: str):
        row = db_buffer.fetch_one(
            "SELECT COUNT(*) AS cnt FROM uplink_buffer WHERE uplink_name = ?",
            (uplink_name,),
        )
        if not row:
            return 0
        # db_helper คืน dict
        return int(row.get("cnt", 0))

