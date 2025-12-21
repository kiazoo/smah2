import json
import requests


class HttpUplink:
    def __init__(self, name: str, url: str, headers: dict):
        self.name = name
        self.url = url
        self.headers = headers or {}

    def send(self, payload: dict):
        if not payload:
            return

        resp = requests.post(
            self.url,
            json=payload,
            headers=self.headers,
            timeout=5,
        )

        if resp.status_code >= 300:
            raise RuntimeError(
                f"HTTP uplink failed status={resp.status_code} body={resp.text}"
            )
