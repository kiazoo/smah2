# services/echo_service.py

import zmq
from core.config import BROKER_CONNECT_ADDRESS
from core import message

SERVICE_NAME = "echo-service"


def main():
    context = zmq.Context.instance()
    socket = context.socket(zmq.DEALER)
    socket.identity = SERVICE_NAME.encode("utf-8")
    socket.connect(BROKER_CONNECT_ADDRESS)

    print(f"[{SERVICE_NAME}] Connected to {BROKER_CONNECT_ADDRESS}")

    # ส่ง register
    reg_msg = {
        "msg_id": message.new_msg_id(),
        "type": "register",
        "src": SERVICE_NAME,
        "dst": "broker",
        "action": "register",
        "service_name": SERVICE_NAME,
        "payload": {},
        "correlation_id": None,
        "timestamp": message.now_iso(),
    }
    socket.send(message.dumps(reg_msg))

    while True:
        frames = socket.recv_multipart()

        # DEALER จะรับแบบ 1 frame (data) หรือ 2 frame ก็ต้องรองรับ
        if len(frames) == 1:
            data = frames[0]
        elif len(frames) == 2:
            _, data = frames  # identity, data
        else:
            print("Unexpected frames:", frames)
            return

        msg = message.loads(data)

        print(f"[{SERVICE_NAME}] received: {msg}")

        if msg.get("type") == "request":
            # ตอบกลับ
            reply = message.build_message(
                msg_type="response",
                src=SERVICE_NAME,
                dst=msg["src"],
                action=msg.get("action"),
                payload={"echo": msg.get("payload")},
                correlation_id=msg.get("msg_id"),
            )
            socket.send(message.dumps(reply))


if __name__ == "__main__":
    main()
