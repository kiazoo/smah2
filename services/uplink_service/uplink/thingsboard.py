import requests
from .base import UplinkBase

class ThingsBoardUplink(UplinkBase):
    def __init__(self, name: str, protocol: str, host: str, token: str):
        super().__init__(name)
        self.protocol = protocol.lower()
        self.host = host
        self.token = token

    def send(self, payload: dict):
        telemetry = self._flatten_payload(payload)

        if not telemetry:
            print("[TB DEBUG] telemetry EMPTY -> skip send", flush=True)
            return

        if self.protocol == "http":
            self._send_http(telemetry)
        elif self.protocol == "mqtt":
            self._send_mqtt(telemetry)
        else:
            raise ValueError(f"unsupported protocol: {self.protocol}")

    # ---------- HTTP ----------
    def _send_http(self, telemetry: dict):
        url = f"https://{self.host}/api/v1/{self.token}/telemetry"

        headers = {
            "Content-Type": "application/json",
        }

        print("========== TB SEND DEBUG ==========")
        print("[TB DEBUG] protocol = https")
        print(f"[TB DEBUG] POST {url}")
        print(f"[TB DEBUG] telemetry = {telemetry}")

        resp = requests.post(
            url,
            headers=headers,
            json=telemetry,
            timeout=5,
            allow_redirects=False,   # << สำคัญมาก
        )

        print(f"[TB DEBUG] HTTP status={resp.status_code}")
        print(f"[TB DEBUG] body={resp.text}")
        print("=================================")

        if resp.status_code in (301, 302, 307, 308):
            raise RuntimeError(
                f"TB redirected status={resp.status_code}, location={resp.headers.get('Location')}"
            )

        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"TB HTTP failed status={resp.status_code}, body={resp.text}"
            )


    # ---------- MQTT (ยังไม่ใช้ก็ได้) ----------
    def _send_mqtt(self, telemetry: dict):
        raise NotImplementedError("TB MQTT not implemented yet")

    # ---------- FLATTEN ----------
    def _flatten_payload(self, payload: dict) -> dict:
        flat = {}

        services = payload.get("services", {})
        if isinstance(services, dict):
            for svc, data in services.items():
                if isinstance(data, dict):
                    for k, v in data.items():
                        flat[f"{svc}_{k}"] = v
                else:
                    flat[svc] = data

        health = payload.get("health", {})
        if isinstance(health, dict):
            for section, data in health.items():
                if isinstance(data, dict):
                    for k, v in data.items():
                        flat[f"health_{section}_{k}"] = v
                else:
                    flat[f"health_{section}"] = data

        return flat
