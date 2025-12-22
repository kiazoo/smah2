import zmq
import time
import yaml
import os

from shared.zmq_helper.message import build, loads, dumps
from shared.logger_client.client import LoggerClient
from .waveshare_8ch import Waveshare8CH


def load_config():
    base = os.path.dirname(__file__)
    with open(os.path.join(base, "config.yaml")) as f:
        return yaml.safe_load(f)


def bytes_to_hex(b):
    return " ".join(f"{x:02X}" for x in b)


def send_raw(sock, driver, serial_cfg, frame):
    sock.send(dumps(build(
        "request",
        "io_control_service",
        driver,
        "modbus.send_raw",
        {
            "serial": serial_cfg,
            "hex": bytes_to_hex(frame)
        }
    )))
    frames = sock.recv_multipart()
    resp = loads(frames[-1])
    return bytes.fromhex(resp["payload"]["hex"])


def main():
    cfg = load_config()

    service_name = cfg["service"]["name"]
    endpoint = cfg["comm_core"]["endpoint"]
    driver = cfg["driver"]["service_name"]
    interval = cfg["polling"]["interval_sec"]
    devices = cfg["rtu_devices"]

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = service_name.encode()
    sock.connect(endpoint)

    sock.send(dumps(build("register", service_name, "broker", "register")))
 

    while True:
        snapshot = {}

        for dev in devices:
            sid = dev["slave_id"]
            serial_cfg = {
                "baudrate": dev["baudrate"],
                "parity": "N",
                "stopbits": 1,
                "bytesize": 8,
                "timeout": 1.0
            }

            di = Waveshare8CH.parse_bits(
                send_raw(sock, driver, serial_cfg, Waveshare8CH.read_di(sid))
            )
            do = Waveshare8CH.parse_bits(
                send_raw(sock, driver, serial_cfg, Waveshare8CH.read_do(sid))
            )

            snapshot[dev["name"]] = {"di": di, "do": do}

        sock.send(dumps(build(
            "event",
            service_name,
            "uplink_service",
            "push_data",
            {"source": "io_control", "data": snapshot}
        )))

        time.sleep(interval)


if __name__ == "__main__":
    main()
