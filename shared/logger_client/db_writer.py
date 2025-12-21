import json
from shared.db_helper import db_log

def write_log(record):
    db_log.execute(
        """
        INSERT INTO logs(timestamp, level, service, message, trace_id, extra)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record["timestamp"],
            record["level"],
            record["service"],
            record["message"],
            record.get("trace_id"),
            json.dumps(record.get("extra", {})),
        ),
    )
