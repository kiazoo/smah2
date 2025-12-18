from pathlib import Path
from .connection import manager

def init_schema(db_path, schema_file):
    schema_path = Path(schema_file)
    if not schema_path.exists():
        raise FileNotFoundError(schema_file)

    conn = manager.get(db_path)
    cur = conn.cursor()

    sql = schema_path.read_text()
    cur.executescript(sql)
    conn.commit()
