import time
import uuid
import zmq

BROKER = "tcp://127.0.0.1:5555"

def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

def recv_all(sock, poller, timeout_ms=800):
    out = []
    t_end = time.time() + (timeout_ms / 1000.0)
    while time.time() < t_end:
        events = dict(poller.poll(timeout=100))
        if sock in events:
            frames = sock.recv_multipart()
            out.append(frames[-1])
    return out

def try_variant(name, sock, poller, msg: dict, wait_ms=900):
    print(f"\n=== {name} ===")
    print("SEND:", msg)
    sock.send_json(msg)

    raws = recv_all(sock, poller, timeout_ms=wait_ms)
    if not raws:
        print("NO RESPONSE")
        return False

    ok = False
    for raw in raws:
        try:
            resp = zmq.utils.jsonapi.loads(raw)
        except Exception:
            try:
                resp = raw.decode("utf-8", errors="replace")
            except Exception:
                resp = raw
        print("IN :", resp)

        if isinstance(resp, dict):
            # เกณฑ์หลวม ๆ: เจอ response action=register + status ok ก็ถือว่า ACK
            if resp.get("type") == "response" and resp.get("action") == "register":
                st = (resp.get("payload") or {}).get("status")
                if st == "ok":
                    ok = True
    return ok

def main():
    service_name = "modbus_driver_service"

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = service_name.encode()
    sock.connect(BROKER)

    poller = zmq.Poller()
    poller.register(sock, zmq.POLLIN)

    # Variant A: type=register (เหมือนบางโปรเจค)
    msg_id = str(uuid.uuid4())
    vA = {
        "msg_id": msg_id,
        "type": "register",
        "src": service_name,
        "dst": "broker",
        "action": "register",
        "service_name": service_name,
        "payload": {},
        "correlation_id": None,
        "timestamp": now_iso(),
    }

    # Variant B: type=request + action=register (เหมือนระบบที่ทุกอย่างเป็น request/response)
    msg_id = str(uuid.uuid4())
    vB = {
        "msg_id": msg_id,
        "type": "request",
        "src": service_name,
        "dst": "broker",
        "action": "register",
        "payload": {"service_name": service_name},
        "correlation_id": None,
        "timestamp": now_iso(),
    }

    # Variant C: type=request + มี service_name ที่ root + ใน payload (กัน broker เขียนแบบไหนไว้)
    msg_id = str(uuid.uuid4())
    vC = {
        "msg_id": msg_id,
        "type": "request",
        "src": service_name,
        "dst": "broker",
        "action": "register",
        "service_name": service_name,
        "payload": {"service_name": service_name},
        "correlation_id": None,
        "timestamp": now_iso(),
    }

    # Variant D: type=register + payload มี service_name (อีกสไตล์ที่เจอบ่อย)
    msg_id = str(uuid.uuid4())
    vD = {
        "msg_id": msg_id,
        "type": "register",
        "src": service_name,
        "dst": "broker",
        "action": "register",
        "payload": {"service_name": service_name},
        "correlation_id": None,
        "timestamp": now_iso(),
    }

    # ยิงทีละแบบ (เว้นนิดให้ broker จัดการ)
    for name, msg in [("Variant A", vA), ("Variant B", vB), ("Variant C", vC), ("Variant D", vD)]:
        ok = try_variant(name, sock, poller, msg)
        if ok:
            print(f"\n✅ BROKER ACK OK with {name}")
            return
        time.sleep(0.3)

    print("\n❌ ไม่มี variant ไหนได้ ACK -> ต้องดู register schema ของ log_service/platform integrate แบบเป๊ะ ๆ")

if __name__ == "__main__":
    main()
