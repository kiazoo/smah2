import requests
from .base import UplinkBase

class HttpUplink(UplinkBase):
    def __init__(self, name: str, url: str, headers: dict | None = None, timeout_sec: int = 5):
        super().__init__(name)
        self.url = url
        self.headers = headers or {}
        self.timeout_sec = timeout_sec

    def send(self, payload: dict) -> None:
        r = requests.post(self.url, json=payload, headers=self.headers, timeout=self.timeout_sec)
        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError(f"HTTP uplink failed status={r.status_code}, body={r.text[:200]}")
