import json
import uuid
import time
from typing import Optional


def build_message(
    msg_type: str,
    src: str,
    dst: str,
    action: str,
    payload: Optional[dict] = None,
    correlation_id: Optional[str] = None
) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": msg_type,          # register | request | response
        "src": src,
        "dst": dst,
        "action": action,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "timestamp": int(time.time())
    }


def dumps(msg: dict) -> bytes:
    return json.dumps(msg, ensure_ascii=False).encode("utf-8")


def loads(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))
