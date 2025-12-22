import zmq
import yaml
import os
import time

from shared.zmq_helper.message import build, loads, dumps
from shared.logger_client.client import LoggerClient
from .serial_manager import SerialManager


def load_config():
    base = os.path.dirname(__file__)
    with open(os.path.join(base, "config.yaml")) as f:
        return yaml.safe_load(f)


def hex_to_bytes(s):
    return bytes.fromhex(s)


def bytes_to_hex(b):
    return " ".join(f"{x:02X}" for x in b)


def main():
    cfg = load_config()

    service_name = cfg["service"]["name"]
    endpoint = cfg["comm_core"]["endpoint"]
    port = cfg["serial"]["port"]

    logger = LoggerClient(service_name)
    logger.level = cfg["log"]["level"]


    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = service_name.encode()
    sock.connect(endpoint)

    sock.send(dumps(build("register", service_name, "broker", "register")))
    logger.info("modbus_driver_service started", extra={"port": port})

    while True:
        frames = sock.recv_multipart()
        msg = loads(frames[-1])

        if msg["action"] != "modbus.send_raw":
            continue

        payload = msg["payload"]
        serial_cfg = payload["serial"]
        hex_cmd = payload["hex"]

        try:
            tx = hex_to_bytes(hex_cmd)
            rx = serial_mgr.send_raw(serial_cfg, tx)

            resp = {
                "ok": True,
                "hex": bytes_to_hex(rx),
                "rtt_ms": int(time.time() * 1000),
            }
        except Exception as e:
            logger.error("modbus error", extra={"error": str(e)})
            resp = {"ok": False, "error": str(e)}

        sock.send(dumps(build(
            "response",
            service_name,
            msg["src"],
            msg["action"],
            resp,
            msg["msg_id"]
        )))


if __name__ == "__main__":
    main()
