import requests
from .base import UplinkBase
from .mqtt import MqttUplink


class ThingsBoardUplink(UplinkBase):
    """
    Supports:
    - HTTP telemetry: POST http://host/api/v1/{token}/telemetry
    - MQTT telemetry: topic v1/devices/me/telemetry with token as username
    """

    def __init__(self, name: str, protocol: str, host: str, token: str, timeout_sec: int = 5):
        super().__init__(name)
        self.protocol = (protocol or "http").lower()
        self.host = host
        self.token = token
        self.timeout_sec = timeout_sec

        if self.protocol == "mqtt":
            self.mqtt = MqttUplink(
                name=name,
                host=host,
                port=1883,
                topic="v1/devices/me/telemetry",
                username=token,
                password="",
                qos=1,
            )
        else:
            self.mqtt = None

    def _flatten_payload(self, payload: dict) -> dict:
        """
        Convert aggregated payload to ThingsBoard telemetry format (flat key-value).
        """
        flat = {}

        services = payload.get("services", {})
        if isinstance(services, dict):
            for svc, data in services.items():
                if isinstance(data, dict):
                    for k, v in data.items():
                        flat[f"{svc}_{k}"] = v

        health = payload.get("health", {})
        if isinstance(health, dict):
            for section, data in health.items():
                if isinstance(data, dict):
                    for k, v in data.items():
                        flat[f"health_{section}_{k}"] = v

        return flat

    def send(self, payload: dict) -> None:
        print("\n========== TB SEND DEBUG ==========", flush=True)
        print(f"[TB DEBUG] protocol = {self.protocol}", flush=True)
        print(f"[TB DEBUG] raw payload = {payload}", flush=True)

        telemetry = self._flatten_payload(payload)
        print(f"[TB DEBUG] flattened telemetry = {telemetry}", flush=True)

        if not telemetry:
            print("[TB DEBUG] telemetry EMPTY -> skip send", flush=True)
            print("=================================\n", flush=True)
            return

        if self.protocol == "mqtt":
            print("[TB DEBUG] send via MQTT", flush=True)
            self.mqtt.send(telemetry)
            print("=================================\n", flush=True)
            return

        url = f"http://{self.host}/api/v1/{self.token}/telemetry"
        print(f"[TB DEBUG] POST {url}", flush=True)

        r = requests.post(url, json=telemetry, timeout=self.timeout_sec)
        print(
            f"[TB DEBUG] HTTP status={r.status_code} body={r.text}",
            flush=True,
        )
        print("=================================\n", flush=True)

        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError(
                f"TB HTTP failed status={r.status_code}, body={r.text[:200]}"
            )
