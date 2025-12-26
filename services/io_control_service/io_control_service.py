"""
I/O control service for Smartshop AI.

This service polls a set of Modbus RTU devices (e.g. Waveshare 8‑CH modules) via
the modbus driver service.  It sends raw read requests for discrete inputs
and coils, parses the bitfields and publishes the snapshot to the uplink
service.  The service now includes error handling to cope with driver
responses that indicate failure and uses per‑device serial configuration
parameters from the YAML config.

Usage:
    python services/io_control_service/io_control_service.py
"""

import os
import time
import yaml
import zmq

from shared.zmq_helper.message import build, loads, dumps
from shared.logger_client.client import LoggerClient
from .waveshare_8ch import Waveshare8CH


def load_config() -> dict:
    """Load YAML configuration relative to this file."""
    base = os.path.dirname(__file__)
    with open(os.path.join(base, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def bytes_to_hex(b: bytes) -> str:
    """Convert bytes to an uppercase space‑separated hex string."""
    return " ".join(f"{x:02X}" for x in b)


def send_raw(sock: zmq.Socket, driver: str, serial_cfg: dict, frame: bytes, logger: LoggerClient) -> bytes:
    """
    Send a raw Modbus RTU frame to the driver and return the response bytes.

    This helper wraps the request/response pattern and adds error handling.
    If the driver indicates an error or the response is missing, an empty
    bytes object is returned and the error is logged.
    """
    # Build and send request message
    req = build(
        msg_type="request",
        src="io_control_service",
        dst=driver,
        action="modbus.send_raw",
        payload={"serial": serial_cfg, "hex": bytes_to_hex(frame)},
    )
    sock.send(dumps(req))
    # Wait for reply from driver
    frames = sock.recv_multipart()
    resp = loads(frames[-1])
    payload = resp.get("payload", {})
    # Handle error responses
    if not payload.get("ok"):
        err = payload.get("error", "unknown error")
        logger.error(
            "modbus driver returned error",
            extra={"error": err, "frame_hex": bytes_to_hex(frame)},
        )
        return b""
    hex_resp = payload.get("hex")
    if not hex_resp:
        logger.error(
            "modbus driver response missing hex",
            extra={"response": payload},
        )
        return b""
    try:
        return bytes.fromhex(hex_resp)
    except Exception as e:
        logger.error(
            "failed to parse hex response",
            extra={"error": str(e), "hex": hex_resp},
        )
        return b""


def main() -> None:
    cfg = load_config()
    service_cfg = cfg.get("service", {})
    comm_cfg = cfg.get("comm_core", {})
    driver_cfg = cfg.get("driver", {})
    polling_cfg = cfg.get("polling", {})
    devices = cfg.get("rtu_devices", [])
    log_cfg = cfg.get("log", {})

    service_name = service_cfg.get("name", "io_control_service")
    endpoint = comm_cfg.get("endpoint", "tcp://127.0.0.1:5555")
    driver_name = driver_cfg.get("service_name", "modbus_driver_service")
    interval = polling_cfg.get("interval_sec", 1)

    # Initialize logger
    logger = LoggerClient(service_name)
    logger.level = log_cfg.get("level", "INFO")
    log_hex = log_cfg.get("log_modbus_hex", False)

    # Prepare ZeroMQ socket
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = service_name.encode()
    sock.connect(endpoint)
    # Register with broker
    reg = build(
        msg_type="register",
        src=service_name,
        dst="broker",
        action="register",
        payload={},
    )
    sock.send(dumps(reg))
    logger.info("io_control_service started", extra={"devices": len(devices)})

    # Poll loop
    while True:
        snapshot: dict[str, dict[str, list[int]]] = {}
        for dev in devices:
            name = dev.get("name") or f"rtu_{dev.get('slave_id', '?')}"
            sid = dev.get("slave_id")
            if sid is None:
                logger.warn("missing slave_id", extra={"device": dev})
                continue
            # Build serial config from device settings with defaults
            serial_cfg = {
                "baudrate": dev.get("baudrate", 9600),
                "parity": dev.get("parity", "N"),
                "stopbits": dev.get("stopbits", 1),
                "bytesize": dev.get("bytesize", 8),
                "timeout": dev.get("timeout", 1.0),
            }
            # Read discrete inputs
            di_frame = Waveshare8CH.read_di(sid)
            if log_hex:
                logger.debug("send DI", extra={"device": name, "hex": bytes_to_hex(di_frame)})
            di_resp = send_raw(sock, driver_name, serial_cfg, di_frame, logger)
            if di_resp:
                di_bits = Waveshare8CH.parse_bits(di_resp)
            else:
                di_bits = []
            # Read coils/discrete outputs
            do_frame = Waveshare8CH.read_do(sid)
            if log_hex:
                logger.debug("send DO", extra={"device": name, "hex": bytes_to_hex(do_frame)})
            do_resp = send_raw(sock, driver_name, serial_cfg, do_frame, logger)
            if do_resp:
                do_bits = Waveshare8CH.parse_bits(do_resp)
            else:
                do_bits = []
            snapshot[name] = {"di": di_bits, "do": do_bits}
        # Publish snapshot to uplink_service
        event = build(
            msg_type="event",
            src=service_name,
            dst="uplink_service",
            action="push_data",
            payload={"source": "io_control", "data": snapshot},
        )
        sock.send(dumps(event))
        time.sleep(interval)


if __name__ == "__main__":
    main()