import time


class Aggregator:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.services = {}

    def update_service_data(self, source: str, data: dict):
        self.services[source] = data

    def build_payload(self, health_snapshot=None) -> dict:
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "device_id": self.device_id,
            "services": self.services.copy(),
            "health": health_snapshot,
        }
