import time
import zmq

from shared.zmq_helper.message import dumps, loads, build

class HealthClient:
    def __init__(self, sock, service_name: str, health_service: str, action_snapshot: str, timeout_ms: int = 1200):
        self.sock = sock
        self.service_name = service_name
        self.health_service = health_service
        self.action_snapshot = action_snapshot
        self.timeout_ms = timeout_ms

        # poller for response
        self.poller = zmq.Poller()
        self.poller.register(self.sock, zmq.POLLIN)

    def get_snapshot(self) -> dict | None:
        req = build(
            msg_type="request",
            src=self.service_name,
            dst=self.health_service,
            action=self.action_snapshot,
            payload={},
            correlation_id=None,
        )
        self.sock.send(dumps(req))

        events = dict(self.poller.poll(self.timeout_ms))
        if self.sock not in events:
            return None

        frames = self.sock.recv_multipart()
        msg = loads(frames[-1])
        payload = msg.get("payload")

        # รองรับทั้งรูปแบบ {"ok":true,"data":{...}} หรือส่ง snapshot ตรง ๆ
        if isinstance(payload, dict) and "data" in payload:
            return payload.get("data")
        return payload if isinstance(payload, dict) else None
