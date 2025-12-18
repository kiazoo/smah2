import time


class ServiceRegistry:
    def __init__(self, timeout_sec: int):
        self.timeout = timeout_sec
        self.services = {}

    def update_heartbeat(self, payload: dict):
        key = f"{payload['service']}:{payload['service_id']}"
        self.services[key] = {
            "service": payload["service"],
            "service_id": payload["service_id"],
            "status": payload.get("status", "ok"),
            "last_seen": payload.get("ts", int(time.time())),
        }

    def snapshot(self):
        now = int(time.time())
        alive = dead = 0

        for s in self.services.values():
            if now - s["last_seen"] > self.timeout:
                s["status"] = "dead"
                dead += 1
            else:
                alive += 1

        return {
            "ts": now,
            "summary": {
                "alive": alive,
                "dead": dead
            },
            "services": list(self.services.values())
        }

    def get_service(self, service: str, service_id: str):
        key = f"{service}:{service_id}"
        return self.services.get(key)
