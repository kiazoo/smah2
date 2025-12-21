import time
import json
import yaml
import zmq

from shared.zmq_helper.message import dumps, loads, build
from .handlers import handle_push_data, handle_update_uplink_config

from .aggregator import Aggregator
from .buffer import BufferStore
from .health_client import HealthClient

from .uplink.http import HttpUplink
from .uplink.mqtt import MqttUplink
from .uplink.thingsboard import ThingsBoardUplink
from .config_manager import ConfigManager

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


def _make_dealer(ctx: zmq.Context, identity: str, broker_addr: str) -> zmq.Socket:
    s = ctx.socket(zmq.DEALER)
    s.identity = identity.encode()
    s.setsockopt(zmq.RCVTIMEO, 500)
    s.setsockopt(zmq.LINGER, 0)
    s.connect(broker_addr)
    return s


def _send_register(sock: zmq.Socket, service_name: str):
    reg = {
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
    sock.send(dumps(reg))


def sync_uplinks(uplinks_cfg, uplinks, schedule, interval):
    enabled_names = set()

    for u in uplinks_cfg:
        name = u.get("name")
        if not name:
            continue

        if not u.get("enabled", False):
            continue

        enabled_names.add(name)

        if name not in uplinks:
            uplink = make_uplink(u)
            uplinks[name] = uplink
            interval[name] = int(u.get("interval_sec", 10))
            schedule[name] = time.time() + interval[name]
            print(f"[uplink_service] uplink enabled: {name}", flush=True)
        else:
            interval[name] = int(u.get("interval_sec", 10))
            if name not in schedule:
                schedule[name] = time.time() + interval[name]

    for name in list(uplinks.keys()):
        if name not in enabled_names:
            print(f"[uplink_service] uplink disabled: {name}", flush=True)
            uplinks.pop(name, None)
            schedule.pop(name, None)
            interval.pop(name, None)


def main():
    config_path = "services/uplink_service/config.yaml"
    cfg_mgr = ConfigManager(config_path)

    cfg_mgr.reload_if_changed()
    cfg = cfg_mgr.cfg

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

    uplinks = {}
    schedule = {}
    interval = {}

    sync_uplinks(cfg_mgr.get_uplinks_cfg(), uplinks, schedule, interval)

    aggregator = Aggregator(device_id=device_id)
    buffer_store = BufferStore(max_records=buffer_max)

    ctx = zmq.Context.instance()

    sock = _make_dealer(ctx, SERVICE_NAME, broker_addr)
    _send_register(sock, SERVICE_NAME)

    health_sock = _make_dealer(ctx, f"{SERVICE_NAME}.health", broker_addr)
    _send_register(health_sock, f"{SERVICE_NAME}.health")

    health_client = HealthClient(
        sock=health_sock,
        service_name=f"{SERVICE_NAME}.health",
        health_service=health_service_name,
        action_snapshot=health_action,
        timeout_ms=health_timeout_ms,
    )

    last_flush = time.time()

    print(f"[uplink_service] started device_id={device_id} broker={broker_addr}", flush=True)
    print(f"[uplink_service] uplinks enabled: {list(uplinks.keys())}", flush=True)

    while True:
        # ---------- CONFIG CHECK ----------
        if cfg_mgr.reload_if_changed():
            sync_uplinks(cfg_mgr.get_uplinks_cfg(), uplinks, schedule, interval)
            print(f"[uplink_service] uplinks now: {list(uplinks.keys())}", flush=True)

        # ---------- RECEIVE ----------
        try:
            frames = sock.recv_multipart()
            raw = loads(frames[-1])

            if not isinstance(raw, dict):
                print(f"[uplink_service] DROP non-dict msg: {raw}", flush=True)
                continue

            msg = raw

            action = msg.get("action")
            src = msg.get("src")
            payload = msg.get("payload") or {}

            ok = True
            info = "ok"

            if action == "push_data":
                for name in uplinks.keys():
                    handle_push_data(
                        aggregator,
                        payload,
                        uplink_name=name,
                    )
                print(f"[uplink_service] RECV push_data from={src}", flush=True)

            elif action == "update_uplink_config":
                ok, info = handle_update_uplink_config(
                    config_path=config_path,
                    cfg_mgr=cfg_mgr,
                    payload=payload
                )
                print(f"[uplink_service] RPC update_uplink_config ok={ok} msg={info}", flush=True)

            if msg.get("type") == "request":
                resp = build(
                    msg_type="response",
                    src=SERVICE_NAME,
                    dst=src,
                    action=action,
                    payload={"ok": ok, "message": info},
                    correlation_id=msg.get("msg_id"),
                )
                sock.send(dumps(resp))

        except zmq.Again:
            pass

        # ---------- SEND ----------
        now = time.time()
        for name, uplink in list(uplinks.items()):
            if name not in schedule or name not in interval:
                continue

            if now < schedule[name]:
                continue

            schedule[name] = now + interval[name]

            health = health_client.get_snapshot()
            payload = aggregator.build(uplink_name=name, health_snapshot=health)

            if payload is None:
                continue

            try:
                uplink.send(payload)
                # ✅ success: clear only this uplink bucket + mark health sent
                aggregator.clear(name)
                aggregator.mark_health_sent(name, health)
                print(f"[uplink_service] sent uplink={name}", flush=True)
            except Exception as e:
                if payload.get("services"):
                    buffer_store.enqueue(uplink_name=name, payload=payload)
                    print(f"[uplink_service] SEND FAIL uplink={name} err={e}", flush=True)

        # ---------- FLUSH BUFFER ----------
        if now - last_flush >= flush_interval:
            last_flush = now

            for name, uplink in list(uplinks.items()):
                pending = buffer_store.count(name)
                if pending <= 0:
                    continue

                batch = buffer_store.fetch_batch(name, limit=flush_batch)
                if not batch:
                    continue

                print(f"[uplink_service] flush uplink={name} pending={pending} batch={len(batch)}", flush=True)

                for row in batch:
                    row_id = row["id"]
                    payload_json = row["payload"]

                    try:
                        payload_obj = json.loads(payload_json)
                    except Exception as e:
                        print(f"[uplink_service] DROP invalid JSON id={row_id} err={e}", flush=True)
                        buffer_store.mark_sent(row_id)
                        continue

                    try:
                        uplink.send(payload_obj)
                        buffer_store.mark_sent(row_id)

                        # ✅ ถ้า payload_obj มี health ให้ mark ไว้ กันยิง health ซ้ำไม่รู้จบ
                        aggregator.mark_health_sent(name, payload_obj.get("health"))

                    except Exception as e:
                        buffer_store.inc_retry(row_id)
                        print(f"[uplink_service] FLUSH FAIL uplink={name} id={row_id} err={e}", flush=True)
                        break

        time.sleep(0.05)


if __name__ == "__main__":
    main()
