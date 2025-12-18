import zmq
from shared.zmq_helper.message import build, dumps, loads
from shared.zmq_helper.config import BROKER_ADDRESS


class ZMQClient:
    def __init__(self, service_name):
        self.service_name = service_name
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.identity = service_name.encode()
        self.socket.connect(BROKER_ADDRESS)

    def register(self):
        msg = {
            "msg_id": "",
            "type": "register",
            "src": self.service_name,
            "dst": "broker",
            "action": "register",
            "service_name": self.service_name,
            "payload": {},
            "correlation_id": None,
            "timestamp": "",
        }
        self.socket.send(dumps(msg))
        return self.recv()

    def send_request(self, dst, action, payload=None):
        msg = build(
            msg_type="request",
            src=self.service_name,
            dst=dst,
            action=action,
            payload=payload,
        )
        self.socket.send(dumps(msg))

    def recv(self):
        frames = self.socket.recv_multipart()
        
        if len(frames) == 1:
            data = frames[0]
        elif len(frames) == 2:
            _, data = frames
        else:
            raise ValueError(f"Unexpected ZMQ frame: {frames}")

        return loads(data)
