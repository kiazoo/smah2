import time
import json
import yaml
import zmq

from shared.zmq_helper.message import dumps, loads, build

from .aggregator import Aggregator
from .buffer import BufferStore
from .health_client import HealthClient
from .handlers import handle_push_data, handle_update_uplink_config

from .uplink.http import HttpUplink
from .uplink.mqtt import MqttUplink
from .uplink.thingsboard import ThingsBoardUplink
from .config_manager import ConfigManager

SERVICE_NAME = "uplink_service"


# ---------- HELPERS ----------
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


def _make_dealer(ctx: zmq.Context, identity: str, broker_addr: str) -> zmq.Socket:
    s = ctx.socket(zmq.DEALER)
    s.identity = identity.encode()
    s.setsockopt(zmq.RCVTIMEO, 500)
    s.setsockopt(zmq.LINGER, 0)
    s.connect(broker_addr)
    return s


def _send_register(sock: zmq.Socket, service_name: str):
    sock.send(
        dumps(
            {
                "msg_id": "",
                "type": "register",
                "src": service_name,
                "dst": "broker",
                "action": "register",
                "service_name": service_name,
                "payload": {},
                "correlation_id": None,
                "timestamp": "",
            }
        )
    )


def sync_uplinks(uplinks_cfg, uplinks, schedule, interval):
    enabled = set()

    for u in uplinks_cfg:
        name = u.get("name")
        if not name or not u.get("enabled", False):
            continue

        enabled.add(name)

        if name not in uplinks:
            uplinks[name] = make_uplink(u)
            interval[name] = int(u.get("interval_sec", 10))
            schedule[name] = time.time() + interval[name]
            print(f"[uplink_service] uplink enabled: {name}", flush=True)
        else:
            interval[name] = int(u.get("interval_sec", 10))

    for name in list(uplinks.keys()):
        if name not in enabled:
            print(f"[uplink_service] uplink disabled: {name}", flush=True)
            uplinks.pop(name)
            schedule.pop(name, None)
            interval.pop(name, None)


# ---------- MAIN ----------
def main():
    config_path = "services/uplink_service/config.yaml"
    cfg_mgr = ConfigManager(config_path)
    cfg_mgr.reload_if_changed()

    cfg = cfg_mgr.cfg

    device_id = cfg.get("device", {}).get("id", "SMARTSHOP-UNKNOWN")
    broker_addr = cfg.get("broker", {}).get("address", "tcp://127.0.0.1:5555")

    buffer_cfg = cfg.get("buffer", {})
    buffer_store = BufferStore(max_records=int(buffer_cfg.get("max_records", 1000)))
    flush_batch = int(buffer_cfg.get("flush_batch", 50))
    flush_interval = int(buffer_cfg.get("flush_interval_sec", 5))

    uplinks = {}
    schedule = {}
    interval = {}

    sync_uplinks(cfg_mgr.get_uplinks_cfg(), uplinks, schedule, interval)

    aggregator = Aggregator(device_id=device_id)

    ctx = zmq.Context.instance()
    sock = _make_dealer(ctx, SERVICE_NAME, broker_addr)
    _send_register(sock, SERVICE_NAME)

    health_cfg = cfg.get("health", {})
    health_client = HealthClient(
        sock=_make_dealer(ctx, f"{SERVICE_NAME}.health", broker_addr),
        service_name=f"{SERVICE_NAME}.health",
        health_service=health_cfg.get("service_name", "health-service"),
        action_snapshot=health_cfg.get("action_snapshot", "get_snapshot"),
        timeout_ms=int(health_cfg.get("timeout_ms", 1200)),
    )

    last_flush = time.time()

    print(f"[uplink_service] started device_id={device_id} broker={broker_addr}", flush=True)
    print(f"[uplink_service] uplinks enabled: {list(uplinks.keys())}", flush=True)

    while True:
        # ---- reload config ----
        if cfg_mgr.reload_if_changed():
            sync_uplinks(cfg_mgr.get_uplinks_cfg(), uplinks, schedule, interval)

        # ---- receive ----
        try:
            msg = loads(sock.recv_multipart()[-1])
            if not isinstance(msg, dict):
                continue

            action = msg.get("action")
            payload = msg.get("payload") or {}
            src = msg.get("src")

            ok, info = True, "ok"

            if action == "push_data":
                for name in uplinks.keys():
                    handle_push_data(aggregator, payload, name)

                print(f"[uplink_service] RECV push_data from={src}", flush=True)

            elif action == "update_uplink_config":
                ok, info = handle_update_uplink_config(config_path, cfg_mgr, payload)
                print(f"[uplink_service] RPC update_uplink_config ok={ok} msg={info}", flush=True)

            if msg.get("type") == "request":
                sock.send(
                    dumps(
                        build(
                            msg_type="response",
                            src=SERVICE_NAME,
                            dst=src,
                            action=action,
                            payload={"ok": ok, "message": info},
                            correlation_id=msg.get("msg_id"),
                        )
                    )
                )

        except zmq.Again:
            pass

        # ---- send uplinks ----
        now = time.time()
        health = health_client.get_snapshot()

        for name, uplink in list(uplinks.items()):
            if now < schedule.get(name, 0):
                continue

            schedule[name] = now + interval[name]
            payload = aggregator.build(name, health)

            if payload is None:
                continue

            try:
                uplink.send(payload)
                aggregator.clear(name)
                aggregator.mark_health_sent(name, health)
                print(f"[uplink_service] sent uplink={name}", flush=True)

            except Exception as e:
                if payload.get("services"):
                    buffer_store.enqueue(name, payload)
                    print(f"[uplink_service] SEND FAIL uplink={name} err={e}", flush=True)

        # ---- flush buffer ----
        if now - last_flush >= flush_interval:
            last_flush = now

            for name, uplink in list(uplinks.items()):
                batch = buffer_store.fetch_batch(name, flush_batch)
                if not batch:
                    continue

                print(f"[uplink_service] flush uplink={name} batch={len(batch)}", flush=True)

                for row in batch:
                    try:
                        payload = json.loads(row["payload"])
                        uplink.send(payload)
                        buffer_store.mark_sent(row["id"])
                    except Exception as e:
                        buffer_store.inc_retry(row["id"])
                        print(f"[uplink_service] FLUSH FAIL uplink={name} id={row['id']} err={e}", flush=True)
                        break

        time.sleep(0.05)


if __name__ == "__main__":
    main()
