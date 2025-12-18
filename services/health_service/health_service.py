import time
import json
import uuid
import yaml
import logging
import zmq
import subprocess
import os

from .hw_collect import collect_hw_snapshot

# =========================
# Protocol helper (local)
# =========================

class ServiceState:
    INIT = "INIT"
    RUNNING = "RUNNING"
    TIMEOUT = "TIMEOUT"
    RESTARTING = "RESTARTING"
    FAILED = "FAILED"


def build_message(
    msg_type: str,
    src: str,
    dst: str,
    action: str,
    payload: dict | None = None,
    correlation_id: str | None = None,
):
    return {
        "msg_id": str(uuid.uuid4()),
        "type": msg_type,          # register | request | response
        "src": src,
        "dst": dst,
        "action": action,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "timestamp": int(time.time()),
    }


def dumps(msg: dict) -> bytes:
    return json.dumps(msg, ensure_ascii=False).encode("utf-8")


def loads(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


# =========================
# Registry
# =========================

class ServiceRegistry:
    def __init__(self, timeout_sec: int):
        self.timeout = timeout_sec
        self.services = {}

    def detect_timeouts(self):
        now = int(time.time())
        for s in self.services.values():
            last = s.get("last_seen", 0)
            if now - last > self.timeout:
                if s.get("state") == ServiceState.RUNNING:
                    s["state"] = ServiceState.TIMEOUT


    def update_heartbeat(self, payload: dict):
        key = f"{payload['service']}:{payload['service_id']}"
        now = int(time.time())

        s = self.services.get(key, {})
        s.update({
            "service": payload["service"],
            "service_id": payload["service_id"],
            "status": payload.get("status", "ok"),
            "last_seen": payload.get("ts", now),
            "state": ServiceState.RUNNING,
            "retry": s.get("retry", 0),
            "last_restart": s.get("last_restart", 0),
        })
        self.services[key] = s


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
                "dead": dead,
            },
            "services": list(self.services.values()),
        }

    def get_service(self, service: str, service_id: str):
        return self.services.get(f"{service}:{service_id}")


# =========================
# Main
# =========================

def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(base_dir, "config.yaml")
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f)



def load_service_specs(cfg):
    specs = {}
    for s in cfg.get("services", []):
        specs[s["service_id"]] = {
            "name": s["name"],
            "enabled": s.get("enabled", True),
            "exec": s.get("exec", {}),
            "policy": s.get("policy", {}),
        }
    return specs


def detect_timeouts(self):
    now = int(time.time())
    for s in self.services.values():
        if now - s["last_seen"] > self.timeout:
            if s.get("state") == ServiceState.RUNNING:
                s["state"] = ServiceState.TIMEOUT

def try_restart(service, spec):
    policy = spec.get("policy", {})
    max_retry = policy.get("max_retry", 0)
    cooldown = policy.get("cooldown_sec", 0)
    now = time.time()

    if service["retry"] >= max_retry:
        service["state"] = ServiceState.FAILED
        return False

    if now - service["last_restart"] < cooldown:
        return False

    cmd = spec.get("exec", {}).get("restart")
    if not cmd:
        service["state"] = ServiceState.FAILED
        return False

    subprocess.Popen(cmd, shell=True)
    service["retry"] += 1
    service["last_restart"] = now
    service["state"] = ServiceState.RESTARTING
    return True

def escalate_failure(sock, service):
    msg = build_message(
        msg_type="request",
        src=SERVICE_NAME,
        dst="platform-gateway",
        action="service.failed",
        payload={
            "service": service["service"],
            "service_id": service["service_id"],
            "retry": service["retry"],
            "ts": int(time.time()),
        },
    )
    sock.send(dumps(msg))

def main():
    cfg = load_config()
    service_specs = load_service_specs(cfg)

    SERVICE_NAME = cfg["service"]["name"]
    ENDPOINT = cfg["comm_core"]["endpoint"]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | health-service | %(message)s",
    )
    log = logging.getLogger()

    # ---- ZMQ DEALER ----
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.setsockopt(zmq.IDENTITY, SERVICE_NAME.encode())
    sock.connect(ENDPOINT)

    # ---- REGISTER ----
    reg_msg = build_message(
        msg_type="register",
        src=SERVICE_NAME,
        dst="broker",
        action="register",
        payload={"service_name": SERVICE_NAME},
    )
    sock.send(dumps(reg_msg))
    log.info("registered with broker")

    registry = ServiceRegistry(
        timeout_sec=cfg["health"]["heartbeat_timeout_sec"]
    )

    auto_cfg = cfg.get("auto_publish", {})
    auto_enabled = auto_cfg.get("enabled", False)
    auto_interval = auto_cfg.get("interval_sec", 5)
    auto_targets = auto_cfg.get("targets", [])

    last_auto_publish = 0

    log.info("health-service started")

    while True:
        # ---- RECEIVE ----
        if sock.poll(100):
            frames = sock.recv_multipart()

            msg = None
            for f in frames:
                if f:
                    try:
                        msg = loads(f)
                    except Exception:
                        msg = None
                    break

            if not msg:
                continue

            mtype = msg.get("type")
            action = msg.get("action")

            # ---- HEARTBEAT ----
            if mtype == "request" and action == "health.heartbeat":
                print("[DEBUG] recv action =", action)
                registry.update_heartbeat(msg["payload"])

            # ---- SNAPSHOT REQUEST ----
            elif mtype == "request" and action == "health.snapshot.get":
                snap = registry.snapshot()
                print("[DEBUG] recv action =", action)
                resp = build_message(
                    msg_type="response",
                    src=SERVICE_NAME,
                    dst=msg["src"],
                    action="health.snapshot",
                    payload=snap,
                    correlation_id=msg["msg_id"],
                )
                sock.send(dumps(resp))

            # ---- SERVICE STATUS REQUEST ----
            elif mtype == "request" and action == "health.service.get":
                p = msg["payload"]
                data = registry.get_service(p["service"], p["service_id"])
                print("[DEBUG] recv action =", action)
                resp = build_message(
                    msg_type="response",
                    src=SERVICE_NAME,
                    dst=msg["src"],
                    action="health.service",
                    payload=data,
                    correlation_id=msg["msg_id"],
                )
                sock.send(dumps(resp))
            
            # ---- HW Status STATUS REQUEST ----
            elif mtype == "request" and action == "health.hw.get":
                snap = registry.snapshot()
                snap["hardware"] = collect_hw_snapshot()
                print("[DEBUG] recv action =", action)
                resp = build_message(
                    msg_type="response",
                    src=SERVICE_NAME,
                    dst=msg["src"],
                    action="health.snapshot",
                    payload=snap,
                    correlation_id=msg["msg_id"],
                )
                sock.send(dumps(resp))


        registry.detect_timeouts()

        # ---- Restart Controller ----
        for key, s in registry.services.items():
            if s.get("state") == ServiceState.TIMEOUT:
                spec = service_specs.get(s["service_id"])
                if spec:
                    try_restart(s, spec)

            # ---- Send alert ----
            if s.get("state") == ServiceState.FAILED:
                escalate_failure(sock, s)
            

        # ---- AUTO PUBLISH ----
        now = time.time()
        if auto_enabled and now - last_auto_publish >= auto_interval:
            snap = registry.snapshot()

            for tgt in auto_targets:
                out = build_message(
                    msg_type="request",
                    src=SERVICE_NAME,
                    dst=tgt["service"],
                    action=tgt["action"],
                    payload=snap,
                )
                sock.send(dumps(out))

            last_auto_publish = now

        time.sleep(0.05)


if __name__ == "__main__":
    main()
