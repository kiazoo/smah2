import json
from shared.db_helper import db_log

MAX_LOGS = 1000

def handle_log(record: dict) -> dict:
    # validate minimal fields
    for k in ("timestamp", "level", "service", "message"):
        if k not in record:
            return {"ok": False, "error": f"missing field: {k}"}

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

    # FIFO keep last 1000
    db_log.execute(
        f"""
        DELETE FROM logs
        WHERE id NOT IN (
            SELECT id FROM logs
            ORDER BY id DESC
            LIMIT {MAX_LOGS}
        )
        """
    )

    return {"ok": True}

def handle_query(params: dict) -> dict:
    level = params.get("level")
    service = params.get("service")
    limit = int(params.get("limit", 100))
    limit = max(1, min(limit, 1000))

    where = []
    sql_params = []

    if level:
        where.append("level = ?")
        sql_params.append(level)
    if service:
        where.append("service = ?")
        sql_params.append(service)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db_log.fetch_all(
        f"""
        SELECT id, timestamp, level, service, message, trace_id, extra
        FROM logs
        {where_sql}
        ORDER BY id DESC
        LIMIT ?
        """,
        sql_params + [limit],
    )

    return {"ok": True, "rows": rows}
