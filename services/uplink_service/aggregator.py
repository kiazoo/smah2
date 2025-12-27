from typing import Dict
import copy
import time


class Aggregator:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self._store: Dict[str, Dict[str, Dict]] = {}
        self._dirty: Dict[str, bool] = {}

    def update(self, uplink_name: str, source: str, data: Dict):
        if uplink_name not in self._store:
            self._store[uplink_name] = {}

        # overwrite ล่าสุดของ source นั้น
        self._store[uplink_name][source] = copy.deepcopy(data)
        self._dirty[uplink_name] = True

        print(
            f"[DEBUG][agg.update] uplink={uplink_name} source={source} keys={list(data.keys())}",
            flush=True
        )

    def build(self, uplink_name: str, health_snapshot: Dict | None = None):
        if not self._dirty.get(uplink_name):
            return None

        services = self._store.get(uplink_name)
        if not services:
            return None

        payload = {
            "device_id": self.device_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": copy.deepcopy(services),
        }

        if health_snapshot:
            payload["health"] = health_snapshot

        print(
            f"[DEBUG][agg.build] uplink={uplink_name} payload_keys={list(services.keys())}",
            flush=True
        )

        return payload

    def clear(self, uplink_name: str):
        self._dirty[uplink_name] = False
