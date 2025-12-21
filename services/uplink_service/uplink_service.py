import time
import json
import yaml
import zmq

from shared.zmq_helper.message import dumps, loads, build

from .aggregator import Aggregator
from .buffer import BufferStore
from .health_client import HealthClient
from .handlers import handle_push_data

from .uplink.http import HttpUplink
from .uplink.mqtt import MqttUplink
from .uplink.thingsboard import ThingsBoardUplink

SERVICE_NAME = "uplink_service"


def load_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def make_uplink(u: dict):
    t = (u.get("type") or "").lower()
    name = u.get("name") or "unnamed"

    if t == "http":
        return HttpUplink(name=name, url=u["url"], headers=u.get("headers") or {})

    if t == "mqtt":
        srv = u.get("server") or {}
        return MqttUplink(
            name=name,
            host=srv["host"],
            port=int(srv.get("port", 1883)),
            topic=u["topic"],
            username=srv.get("username", ""),
            password=srv.get("password", ""),
            qos=int(u.get("qos", 1)),
        )

    if t == "thingsboard":
        return ThingsBoardUplink(
            name=name,
            protocol=u.get("protocol", "http"),
            host=u["host"],
            token=u["token"],
        )

    raise ValueError(f"unknown uplink type: {t}")


def main():
    cfg = load_cfg("services/uplink_service/config.yaml")

    device_id = cfg.get("device", {}).get("id", "SMARTSHOP-UNKNOWN")
    broker_addr = cfg.get("broker", {}).get("address", "tcp://127.0.0.1:5555")

    health_cfg = cfg.get("health", {})
    health_service_name = health_cfg.get("service_name", "health-service")
    health_action = health_cfg.get("action_snapshot", "get_snapshot")
    health_timeout_ms = int(health_cfg.get("timeout_ms", 1200))

    buffer_cfg = cfg.get("buffer", {})
    buffer_max = int(buffer_cfg.get("max_records", 1000))
    flush_batch = int(buffer_cfg.get("flush_batch", 50))
    flush_interval = int(buffer_cfg.get("flush_interval_sec", 5))

    uplinks_cfg = cfg.get("uplinks", [])

    # Prepare uplinks + schedule
    uplinks = []
    schedule = {}
    interval = {}

    for u in uplinks_cfg:
        if not u.get("enabled", False):
            continue
        obj = make_uplink(u)
        uplinks.append((u, obj))
        interval[obj.name] = int(u.get("interval_sec", 10))
        schedule[obj.name] = time.time() + interval[obj.name]

    aggregator = Aggregator(device_id=device_id)
    buffer_store = BufferStore(max_records=buffer_max)

    # ZMQ setup
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = SERVICE_NAME.encode()
    sock.setsockopt(zmq.RCVTIMEO, 500)
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(broker_addr)

    # register
    reg = {
        "msg_id": "",
        "type": "register",
        "src": SERVICE_NAME,
        "dst": "broker",
        "action": "register",
        "service_name": SERVICE_NAME,
        "payload": {},
        "correlation_id": None,
        "timestamp": "",
    }
    sock.send(dumps(reg))

    health_client = HealthClient(
        sock=sock,
        service_name=SERVICE_NAME,
        health_service=health_service_name,
        action_snapshot=health_action,
        timeout_ms=health_timeout_ms,
    )

    last_flush = time.time()

    print(f"[uplink_service] started device_id={device_id} broker={broker_addr}", flush=True)
    print(f"[uplink_service] uplinks enabled: {[u[1].name for u in uplinks]}", flush=True)

    while True:
        # =====================================================
        # 1) RECEIVE inbound messages
        #    ✅ FIX: handle push_data for ALL message types
        # =====================================================
        try:
            frames = sock.recv_multipart()
            msg = loads(frames[-1])

            mtype = msg.get("type")
            action = msg.get("action")
            src = msg.get("src")
            msg_id = msg.get("msg_id")
            payload = msg.get("payload") or {}

            if action == "push_data":
                handle_push_data(aggregator, payload)
                print(f"[uplink_service] RECV push_data from={src}", flush=True)
                result = {"ok": True}
            else:
                result = {"ok": True}

            # reply ONLY if this is a request
            if mtype == "request":
                resp = build(
                    msg_type="response",
                    src=SERVICE_NAME,
                    dst=src,
                    action=action,
                    payload=result,
                    correlation_id=msg_id,
                )
                sock.send(dumps(resp))

        except zmq.Again:
            pass

        # =====================================================
        # 2) PERIODIC UPLINK SEND
        # =====================================================
        now = time.time()
        for u_cfg, uplink_obj in uplinks:
            name = uplink_obj.name
            if now >= schedule[name]:
                schedule[name] = now + interval[name]

                health = health_client.get_snapshot()
                payload = aggregator.build_payload(health_snapshot=health)

                try:
                    uplink_obj.send(payload)
                    print(f"[uplink_service] sent uplink={name}", flush=True)
                except Exception as e:
                    # do NOT buffer empty payload
                    if payload.get("services") or payload.get("health"):
                        buffer_store.enqueue(uplink_name=name, payload=payload)
                        print(f"[uplink_service] SEND FAIL uplink={name} buffered err={e}", flush=True)
                    else:
                        print(f"[uplink_service] SEND SKIP empty payload uplink={name}", flush=True)

        # =====================================================
        # 3) FLUSH BUFFER
        # =====================================================
        if now - last_flush >= flush_interval:
            last_flush = now

            for u_cfg, uplink_obj in uplinks:
                name = uplink_obj.name
                pending = buffer_store.count(name)
                if pending <= 0:
                    continue

                batch = buffer_store.fetch_batch(name, limit=flush_batch)
                if not batch:
                    continue

                print(f"[uplink_service] flush uplink={name} pending={pending} batch={len(batch)}", flush=True)

                for row_id, ts, payload_json, retry_count in batch:
                    try:
                        payload_obj = json.loads(payload_json)
                    except Exception as e:
                        print(f"[uplink_service] DROP invalid JSON id={row_id} err={e}", flush=True)
                        buffer_store.mark_sent(row_id)
                        continue

                    try:
                        uplink_obj.send(payload_obj)
                        buffer_store.mark_sent(row_id)
                    except Exception as e:
                        buffer_store.inc_retry(row_id)
                        print(f"[uplink_service] FLUSH FAIL uplink={name} id={row_id} err={e}", flush=True)
                        break

        time.sleep(0.05)


if __name__ == "__main__":
    main()
