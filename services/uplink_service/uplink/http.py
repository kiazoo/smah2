import requests

class HttpUplink:
    def __init__(self, name: str, url: str, headers=None):
        self.name = name
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}

    def send(self, payload: dict):
        # 👉 ส่งเฉพาะ payload.payload
        data = payload.get("payload")

        if not isinstance(data, dict):
            print("[HTTP DEBUG] no payload -> skip send", flush=True)
            return False

        resp = requests.post(
            self.url,
            json=data,
            headers=self.headers,
            timeout=5,
        )

        if resp.status_code >= 300:
            raise RuntimeError(
                f"HTTP uplink failed status={resp.status_code} body={resp.text}"
            )

        return True
