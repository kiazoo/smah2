# core/broker.py

import zmq
from zmq import Poller
from .config import BROKER_BIND_ADDRESS
from . import message


class ServiceRegistry:
    """เก็บ mapping service_name -> zmq identity"""

    def __init__(self):
        self.name_to_id: dict[str, bytes] = {}
        self.id_to_name: dict[bytes, str] = {}

    def register(self, identity: bytes, service_name: str):
        self.name_to_id[service_name] = identity
        self.id_to_name[identity] = service_name
        print(f"[REG] {service_name} -> {identity!r}")

    def get_identity(self, service_name: str) -> bytes | None:
        return self.name_to_id.get(service_name)


def main():
    context = zmq.Context.instance()
    socket = context.socket(zmq.ROUTER)
    socket.bind(BROKER_BIND_ADDRESS)

    print(f"[BROKER] Listening on {BROKER_BIND_ADDRESS}")

    poller = Poller()
    poller.register(socket, zmq.POLLIN)

    registry = ServiceRegistry()

    while True:
        events = dict(poller.poll(1000))  # 1 วินาที

        if socket in events and events[socket] == zmq.POLLIN:
            # ROUTER จะได้ frame แบบ [identity][empty][data]
            frames = socket.recv_multipart()

            if len(frames) == 3:
                identity, empty, data = frames
            elif len(frames) == 2:
                identity, data = frames
                empty = b""
            else:
                print(f"[WARN] Unexpected frame format: {frames}")
                continue

            msg = message.loads(data)

            msg_type = msg.get("type")
            src = msg.get("src")
            dst = msg.get("dst")

            # 1) สมัครสมาชิก (register)
            if msg_type == "register":
                service_name = msg.get("service_name") or src
                registry.register(identity, service_name)

                # ส่งตอบกลับยืนยันเฉย ๆ
                reply = message.build_message(
                    msg_type="response",
                    src="broker",
                    dst=service_name,
                    action="register",
                    payload={"status": "ok"},
                    correlation_id=msg.get("msg_id"),
                )
                socket.send_multipart([identity, b"", message.dumps(reply)])
                continue

            # 2) ถ้าเป็น request/response ธรรมดา → route ตาม dst
            if dst:
                target_id = registry.get_identity(dst)
                if not target_id:
                    print(f"[WARN] dst '{dst}' ยังไม่ register")
                    # ยังไม่ส่ง error กลับ เดี๋ยวไว้ version ถัดไป
                    continue

                socket.send_multipart([target_id, b"", data])


if __name__ == "__main__":
    main()
