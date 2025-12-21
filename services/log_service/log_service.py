import zmq
import traceback
import time

from shared.zmq_helper.config import BROKER_ADDRESS
from shared.zmq_helper.message import loads, dumps, build
from shared.logger_client import logger

from .handlers import handle_log, handle_query

SERVICE_NAME = "log-service"

def main():
    print("[log-service] starting...", flush=True)
    print(f"[log-service] broker = {BROKER_ADDRESS}", flush=True)

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = SERVICE_NAME.encode()

    # ⭐ สำคัญ: กัน block ตลอด
    sock.setsockopt(zmq.RCVTIMEO, 1000)   # 1 วินาที
    sock.setsockopt(zmq.LINGER, 0)

    sock.connect(BROKER_ADDRESS)
    print("[log-service] socket connected", flush=True)

    # register
    reg = {
        "msg_id": "",
        "type": "register",
        "src": SERVICE_NAME,
        "dst": "broker",
        "action": "register",
        "service_name": SERVICE_NAME,
        "payload": {},
        "correlation_id": None,
        "timestamp": "",
    }

    print("[log-service] sending register...", flush=True)
    sock.send(dumps(reg))
    print("[log-service] register sent", flush=True)

    logger.info("log_service started")
    print("[log-service] ready, waiting for messages\n", flush=True)

    while True:
        try:
            print("[log-service] waiting recv...", flush=True)
            try:
                frames = sock.recv_multipart()
            except zmq.Again:
                # timeout → ไม่มี message
                continue

            data = frames[-1]
            msg = loads(data)

            mtype = msg.get("type")
            action = msg.get("action")
            src = msg.get("src")
            msg_id = msg.get("msg_id")

            print("--------------------------------------------------", flush=True)
            print(f"[log-service] recv from={src} type={mtype} action={action}", flush=True)

            if mtype != "request":
                print("[log-service] skip non-request", flush=True)
                continue

            payload = msg.get("payload") or {}

            if action == "log":
                print("[log-service] handle LOG", flush=True)
                result = handle_log(payload)

            elif action == "query":
                print("[log-service] handle QUERY", flush=True)
                result = handle_query(payload)

            else:
                print("[log-service] unknown action", flush=True)
                result = {"ok": False, "error": "unknown action"}

            resp = build(
                msg_type="response",
                src=SERVICE_NAME,
                dst=src,
                action=action,
                payload=result,
                correlation_id=msg_id,
            )
            sock.send(dumps(resp))
            print(f"[log-service] reply sent ok={result.get('ok')}\n", flush=True)

        except KeyboardInterrupt:
            print("\n[log-service] interrupted, exit", flush=True)
            break
        except Exception:
            print("[log-service] ERROR", flush=True)
            traceback.print_exc()
            time.sleep(1)

if __name__ == "__main__":
    main()
