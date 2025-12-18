# core/message.py

import json
import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_msg_id() -> str:
    return str(uuid.uuid4())


def build_message(
    msg_type: str,
    src: str,
    dst: str,
    action: str | None = None,
    payload: dict | None = None,
    correlation_id: str | None = None,
) -> dict:
    return {
        "msg_id": new_msg_id(),
        "type": msg_type,          # "request" | "response" | "register" | ...
        "src": src,
        "dst": dst,
        "action": action,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "timestamp": now_iso(),
    }


def dumps(msg: dict) -> bytes:
    """แปลง dict → bytes (JSON)"""
    return json.dumps(msg).encode("utf-8")


def loads(data: bytes) -> dict:
    """แปลง bytes(JSON) → dict"""
    return json.loads(data.decode("utf-8"))