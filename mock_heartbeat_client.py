import time
import json
import uuid
import zmq
import os


# ---------- protocol helper (local) ----------

def build_message(msg_type, src, dst, action, payload=None, correlation_id=None):
    return {
        "msg_id": str(uuid.uuid4()),
        "type": msg_type,
        "src": src,
        "dst": dst,
        "action": action,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "timestamp": int(time.time()),
    }


def dumps(msg):
    return json.dumps(msg, ensure_ascii=False).encode("utf-8")


# ---------- config ----------

SERVICE_NAME = "mock-log-service"
SERVICE_ID = "mock-01"
BROKER_ENDPOINT = "tcp://127.0.0.1:5555"


def main():
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)

    identity = f"{SERVICE_NAME}-{os.getpid()}"
    sock.setsockopt(zmq.IDENTITY, identity.encode())
    sock.connect(BROKER_ENDPOINT)

    # ---- REGISTER ----
    reg = build_message(
        msg_type="register",
        src=SERVICE_NAME,
        dst="broker",
        action="register",
        payload={"service_name": SERVICE_NAME},
    )
    sock.send(dumps(reg))
    print("[heartbeat] registered")

    time.sleep(0.5)

    # ---- HEARTBEAT LOOP ----
    while True:
        hb = build_message(
            msg_type="request",
            src=SERVICE_NAME,
            dst="health-service",
            action="health.heartbeat",
            payload={
                "service": SERVICE_NAME,
                "service_id": SERVICE_ID,
                "status": "ok",
                "ts": int(time.time()),
            },
        )
        sock.send(dumps(hb))
        print("[heartbeat] send", hb["payload"])
        time.sleep(3)


if __name__ == "__main__":
    main()
