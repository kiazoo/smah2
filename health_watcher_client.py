import time
import json
import uuid
import zmq


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


def loads(data):
    return json.loads(data.decode("utf-8"))


# ---------- config ----------

SERVICE_NAME = "health-watcher"
BROKER_ENDPOINT = "tcp://127.0.0.1:5555"


def main():
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.setsockopt(zmq.IDENTITY, SERVICE_NAME.encode())
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
    print("[watcher] registered")

    time.sleep(0.5)

    while True:
        # ---- REQUEST SNAPSHOT ----
        req = build_message(
            msg_type="request",
            src=SERVICE_NAME,
            dst="health-service",
            action="health.hw.get",
            payload={},
        )
        print("[watcher] send health.hw.get")
        sock.send(dumps(req))

        # ---- WAIT RESPONSE ----
        if sock.poll(2000):
            frames = sock.recv_multipart()

            msg = None
            for f in frames:
                if f:
                    try:
                        msg = loads(f)
                    except Exception:
                        msg = None
                    break

            if msg:
                print("\n=== HEALTH SNAPSHOT ===")
                print(json.dumps(msg["payload"], indent=2))

        time.sleep(5)


if __name__ == "__main__":
    main()
