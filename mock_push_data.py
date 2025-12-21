import time
import zmq

from shared.zmq_helper.message import build, dumps

BROKER = "tcp://127.0.0.1:5555"
SERVICE_NAME = "mock_push_data"
DST = "uplink_service"   # ต้องตรงกับ SERVICE_NAME ใน uplink_service

def send_register(sock: zmq.Socket, name: str):
    reg = {
        "msg_id": "",
        "type": "register",
        "src": name,
        "dst": "broker",
        "action": "register",
        "service_name": name,
        "payload": {},
        "correlation_id": None,
        "timestamp": "",
    }
    sock.send(dumps(reg))

def main():
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = SERVICE_NAME.encode()
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(BROKER)

    # register กับ broker ก่อน
    send_register(sock, SERVICE_NAME)

    # ยิง event push_data (ไม่รอ response)
    for i in range(10):
        msg = build(
            msg_type="event",
            src=SERVICE_NAME,
            dst=DST,
            action="push_data",
            payload={
                "source": "sensor_1",
                "data": {
                    "temperature": 28.5 + i * 0.1,
                    "humidity": 65 + i,
                },
            },
            correlation_id=None,
        )
        sock.send(dumps(msg))
        print("push_data sent", i, flush=True)
        time.sleep(1)

if __name__ == "__main__":
    main()
