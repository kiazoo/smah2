import requests

class ThingsBoardUplink:
    def __init__(self, name, protocol, host, token):
        self.name = name
        self.protocol = protocol
        self.host = host.rstrip("/")
        self.token = token

        if protocol != "http":
            raise ValueError("Only HTTP supported")

        self.url = f"{self.host}/api/v1/{self.token}/telemetry"

    def send(self, payload: dict):
        raw = payload.get("payload")
        if not isinstance(raw, dict):
            print("[TB DEBUG] no payload -> skip send", flush=True)
            return False

        telemetry = {}

        for source, blocks in raw.items():
            if not isinstance(blocks, dict):
                continue

            for block_name, block_data in blocks.items():
                if not isinstance(block_data, dict):
                    continue

                for k, v in block_data.items():
                    telemetry[f"{block_name}_{k}"] = v

        if not telemetry:
            print("[TB DEBUG] telemetry EMPTY -> skip send", flush=True)
            return False

        print(f"[TB DEBUG] POST telemetry keys={list(telemetry.keys())}", flush=True)

        resp = requests.post(
            self.url,
            json=telemetry,
            timeout=5,
        )

        if resp.status_code >= 300:
            raise RuntimeError(
                f"ThingsBoard uplink failed status={resp.status_code} body={resp.text}"
            )

        return True
