# services/test_client.py

import zmq
from core.config import BROKER_CONNECT_ADDRESS
from core import message

CLIENT_NAME = "test-client"


def main():
    context = zmq.Context.instance()
    socket = context.socket(zmq.DEALER)
    socket.identity = CLIENT_NAME.encode("utf-8")
    socket.connect(BROKER_CONNECT_ADDRESS)

    print(f"[{CLIENT_NAME}] Connected to {BROKER_CONNECT_ADDRESS}")

    # register ตัวเอง
    reg_msg = {
        "msg_id": message.new_msg_id(),
        "type": "register",
        "src": CLIENT_NAME,
        "dst": "broker",
        "action": "register",
        "service_name": CLIENT_NAME,
        "payload": {},
        "correlation_id": None,
        "timestamp": message.now_iso(),
    }
    socket.send(message.dumps(reg_msg))

    # ส่ง request ไปหา echo-service
    req = message.build_message(
        msg_type="request",
        src=CLIENT_NAME,
        dst="echo-service",
        action="echo",
        payload={"text": "Hello Smartshop Core!"},
    )
    print(f"[{CLIENT_NAME}] send: {req}")
    socket.send(message.dumps(req))

    # รอ response
    while True:
        frames = socket.recv_multipart()

        if len(frames) == 1:
            data = frames[0]
        elif len(frames) == 2:
            _, data = frames
        else:
            print(f"[WARN] Unexpected frame format: {frames}")
            continue

        msg = message.loads(data)
        print(f"[{CLIENT_NAME}] got: {msg}")



if __name__ == "__main__":
    main()
