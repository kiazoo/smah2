import uuid
import json
from datetime import datetime, timezone

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def new_id():
    return str(uuid.uuid4())

def build(msg_type, src, dst, action=None, payload=None, correlation_id=None):
    return {
        "msg_id": new_id(),
        "type": msg_type,
        "src": src,
        "dst": dst,
        "action": action,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "timestamp": now_iso(),
    }

def dumps(msg: dict) -> bytes:
    return json.dumps(msg).encode()

def loads(data: bytes) -> dict:
    return json.loads(data.decode())
