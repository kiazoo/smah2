import json
import time
import yaml
import zmq
import paho.mqtt.client as mqtt

from shared.zmq_helper.message import dumps, build


def load_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    cfg = load_cfg("services/tb_control_service/config.yaml")

    tb_cfg = cfg.get("thingsboard", {})
    tb_host = tb_cfg["host"]
    tb_port = int(tb_cfg.get("port", 1883))
    tb_token = tb_cfg["token"]

    broker_addr = cfg.get("broker", {}).get("address", "tcp://127.0.0.1:5555")
    service_name = cfg.get("service", {}).get("name", "tb_control_service")

    # ---------- ZMQ ----------
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = service_name.encode()
    sock.connect(broker_addr)

    # ---------- MQTT ----------
    def on_connect(client, userdata, flags, rc):
        print(f"[tb_control_service] MQTT connected rc={rc}", flush=True)
        client.subscribe("v1/devices/me/rpc/request/+")
        print("[tb_control_service] subscribed RPC request", flush=True)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception as e:
            print(f"[tb_control_service] invalid JSON err={e}", flush=True)
            return

        method = payload.get("method")
        params = payload.get("params")

        if not method:
            return

        print(f"[tb_control_service] RPC recv method={method}", flush=True)

        # forward only known method
        if method == "update_uplink_config":
            zmq_msg = build(
                msg_type="request",
                src=service_name,
                dst="uplink_service",
                action="update_uplink_config",
                payload=params or {},
                correlation_id=None,
            )
            sock.send(dumps(zmq_msg))
            print("[tb_control_service] forwarded update_uplink_config to uplink_service", flush=True)

        # reply to TB (Two-way RPC)
        # extract request id from topic
        try:
            req_id = msg.topic.split("/")[-1]
            resp_topic = f"v1/devices/me/rpc/response/{req_id}"
            client.publish(resp_topic, json.dumps({"ok": True}))
        except Exception:
            pass

    client = mqtt.Client()
    client.username_pw_set(tb_token)
    client.on_connect = on_connect
    client.on_message = on_message

    print("[tb_control_service] connecting to ThingsBoard MQTT...", flush=True)
    client.connect(tb_host, tb_port, keepalive=60)
    client.loop_start()

    # keep service alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
