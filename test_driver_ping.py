import time
import uuid
import zmq
from zmq.utils import jsonapi

BROKER = "tcp://127.0.0.1:5555"
CLIENT = "modbus_test_client"
DST = "modbus_driver_service"

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

def main():
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = CLIENT.encode()
    sock.connect(BROKER)

    poller = zmq.Poller()
    poller.register(sock, zmq.POLLIN)

    # register client (แบบที่ broker ตอบ OK แน่ๆ)
    reg_id = str(uuid.uuid4())
    reg = {
        "msg_id": reg_id,
        "type": "register",
        "src": CLIENT,
        "dst": "broker",
        "action": "register",
        "service_name": CLIENT,
        "payload": {},
        "correlation_id": None,
        "timestamp": now(),
    }
    sock.send_json(reg)

    # wait reg ack
    t_end = time.time() + 2.0
    while time.time() < t_end:
        ev = dict(poller.poll(200))
        if sock not in ev:
            continue
        frames = sock.recv_multipart()
        msg = jsonapi.loads(frames[-1])
        print("IN =", msg)
        if msg.get("type") == "response" and msg.get("action") == "register" and msg.get("correlation_id") == reg_id:
            break

    # send ping
    req_id = str(uuid.uuid4())
    req = {
        "msg_id": req_id,
        "type": "request",
        "src": CLIENT,
        "dst": DST,
        "action": "ping",
        "payload": {},
        "correlation_id": None,
        "timestamp": now(),
    }
    print("SEND =", req)
    sock.send_json(req)

    # wait ping resp
    t_end = time.time() + 3.0
    while time.time() < t_end:
        ev = dict(poller.poll(200))
        if sock not in ev:
            continue
        frames = sock.recv_multipart()
        msg = jsonapi.loads(frames[-1])
        print("IN =", msg)
        if msg.get("type") == "response" and msg.get("action") == "ping" and msg.get("correlation_id") == req_id:
            print("✅ PING OK")
            return

    raise SystemExit("❌ TIMEOUT ping response")

if __name__ == "__main__":
    main()
