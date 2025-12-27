import os
import time
import uuid
import yaml
import zmq
from zmq.utils import jsonapi

# NOTE: ทำเหมือน modbus_driver_service — ห้าม init LoggerClient ก่อน REGISTER OK
from shared.logger_client.client import LoggerClient

from .waveshare_8ch import Waveshare8CH


# ----------------- helpers (เหมือน driver style) -----------------
def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


# สำหรับ payload ที่ส่งไป uplink-service ต้องมี Z ตามตัวอย่าง
def iso_z():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())



def load_config():
    base = os.path.dirname(__file__)
    with open(os.path.join(base, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(cfg: dict):
    base = os.path.dirname(__file__)
    path = os.path.join(base, "config.yaml")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    os.replace(tmp, path)

def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF

def crc_ok(frame: bytes) -> bool:
    if not frame or len(frame) < 4:
        return False
    data = frame[:-2]
    got_lo = frame[-2]
    got_hi = frame[-1]
    crc = crc16_modbus(data)
    return got_lo == (crc & 0xFF) and got_hi == ((crc >> 8) & 0xFF)

def make_register(service_name: str) -> dict:
    msg_id = str(uuid.uuid4())
    return {
        "msg_id": msg_id,
        "type": "register",
        "src": service_name,
        "dst": "broker",
        "action": "register",
        "service_name": service_name,
        "payload": {},
        "correlation_id": None,
        "timestamp": utc_now(),
    }


def make_event(src: str, dst: str, action: str, payload: dict) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "event",
        "src": src,
        "dst": dst,
        "action": action,
        "payload": payload or {},
        "correlation_id": None,
        "timestamp": utc_now(),
    }


def make_request(src: str, dst: str, action: str, payload: dict) -> dict:
    # request ต้องมี msg_id เพื่อให้ driver เอาไปใส่ correlation_id ตอบกลับ
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "request",
        "src": src,
        "dst": dst,
        "action": action,
        "payload": payload or {},
        "correlation_id": None,
        "timestamp": utc_now(),
    }


def bytes_to_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def parse_hex_string(s: str) -> bytes:
    s = (s or "").strip().replace("0x", "").replace(",", " ").replace("\n", " ")
    parts = [p for p in s.split() if p]
    if not parts:
        return b""
    if len(parts) == 1 and len(parts[0]) % 2 == 0:
        return bytes.fromhex(parts[0])
    return bytes.fromhex("".join(parts))


# ----------------- modbus driver rpc (raw) -----------------
def send_raw(sock: zmq.Socket, poller: zmq.Poller, service_name: str, driver_name: str, serial_cfg: dict, frame: bytes,
             timeout_ms: int, print_debug: bool, log_hex: bool, log_fn):
    req = make_request(
        src=service_name,
        dst=driver_name,
        action="modbus.send_raw",
        payload={"serial": serial_cfg, "hex": bytes_to_hex(frame)},
    )
    req_id = req["msg_id"]

    if print_debug:
        print(f"[{service_name}] -> driver TX req_id={req_id} hex={bytes_to_hex(frame)}", flush=True)
    if log_hex:
        log_fn("debug", "tx", {"req_id": req_id, "tx_hex": bytes_to_hex(frame), "serial": serial_cfg})

    sock.send_json(req)

    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        events = dict(poller.poll(200))
        if sock not in events:
            continue
        frames = sock.recv_multipart()
        msg = jsonapi.loads(frames[-1])

        # รอ response จาก driver ที่ correlation_id == req_id
        if (
            msg.get("type") == "response"
            and msg.get("src") == driver_name
            and msg.get("action") == "modbus.send_raw"
            and msg.get("correlation_id") == req_id
        ):
            payload = msg.get("payload") or {}
            if payload.get("status") != "ok":
                if print_debug:
                    print(f"[{service_name}] <- driver ERROR {payload}", flush=True)
                log_fn("error", "driver error", {"req_id": req_id, "error": payload.get("error")})
                return b""

            rx_hex = payload.get("hex") or ""
            if print_debug:
                print(f"[{service_name}] <- driver RX req_id={req_id} hex={rx_hex}", flush=True)
            if log_hex:
                log_fn("debug", "rx", {"req_id": req_id, "rx_hex": rx_hex, "rtt_ms": payload.get("rtt_ms")})
            try:
                return parse_hex_string(rx_hex)
            except Exception as e:
                log_fn("error", "parse rx hex failed", {"req_id": req_id, "error": str(e), "rx_hex": rx_hex})
                return b""

        # ถ้าไม่ใช่ response ของเรา ปล่อยผ่าน (ไม่ให้ตัน)
        # (ถ้าพี่อยาก queue เก็บ ก็ทำได้ แต่เอาให้วิ่งก่อน)

    log_fn("error", "driver timeout", {"tx_hex": bytes_to_hex(frame)})
    return b""


# ----------------- main -----------------
def main():
    cfg = load_config()

    service_name = (cfg.get("service") or {}).get("name", "io_control_service")
    endpoint = (cfg.get("comm_core") or {}).get("endpoint", "tcp://127.0.0.1:5555")
    driver_name = (cfg.get("driver") or {}).get("service_name", "modbus_driver_service")

    # integrator ปลายทางรับ push_data (ถ้าระบบพี่ใช้ uplink_service ก็ใส่ชื่อนั้น)
    integrator_name = ((cfg.get("platform_integrator") or {}).get("service_name")) or "uplink_service"

    polling_cfg = cfg.get("polling") or {}
    reporting_cfg = cfg.get("reporting") or {}
    log_cfg = cfg.get("log") or {}

    poll_interval = float(polling_cfg.get("interval_sec", 0.5))
    report_interval = float(reporting_cfg.get("interval_sec", 5))
    timeout_ms = int(polling_cfg.get("driver_timeout_ms", 2000))

    log_level = str(log_cfg.get("level", "INFO")).upper()
    log_hex = bool(log_cfg.get("log_modbus_hex", False))
    print_debug = bool(log_cfg.get("print_debug", True))

    devices = cfg.get("rtu_devices") or []

    def p(*args):
        if print_debug:
            print(*args, flush=True)

    # ZMQ
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = service_name.encode("utf-8")
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(endpoint)

    poller = zmq.Poller()
    poller.register(sock, zmq.POLLIN)

    p(f"[{service_name}] connect broker={endpoint} driver={driver_name} integrator={integrator_name}")

    # ----------------- REGISTER (เหมือน driver) -----------------
    while True:
        reg = make_register(service_name)
        p(f"[{service_name}] SEND REGISTER -> {reg}")
        sock.send_json(reg)

        deadline = time.time() + 2.0
        got_ack = False
        while time.time() < deadline:
            events = dict(poller.poll(200))
            if sock not in events:
                continue
            frames = sock.recv_multipart()
            msg = jsonapi.loads(frames[-1])
            p(f"[{service_name}] IN <- {msg}")

            if (
                msg.get("type") == "response"
                and msg.get("action") == "register"
                and msg.get("correlation_id") == reg["msg_id"]
                and (msg.get("payload") or {}).get("status") == "ok"
            ):
                got_ack = True
                p(f"[{service_name}] ✅ REGISTER OK")
                break

        if got_ack:
            break
        p(f"[{service_name}] ❌ REGISTER TIMEOUT -> retry")
        time.sleep(0.5)

    # ----------------- LoggerClient หลัง REGISTER OK -----------------
    logger_identity = f"{service_name}.logger"
    logger = LoggerClient(logger_identity)
    logger.level = log_level

    def log_fn(level: str, msg: str, extra: dict | None = None):
        extra = extra or {}
        extra.setdefault("service", service_name)
        try:
            if level == "debug":
                logger.debug(msg, extra=extra)
            elif level == "info":
                logger.info(msg, extra=extra)
            elif level == "warn":
                logger.warn(msg, extra=extra)
            else:
                logger.error(msg, extra=extra)
        except Exception:
            pass

    p(f"[{service_name}] READY")
    log_fn("info", "io control ready", {"broker": endpoint, "driver": driver_name, "integrator": integrator_name})

    # ----------------- state -----------------
    last_di = {}
    last_do = {}
    last_report = time.monotonic()

    # enforce normal mode (optional)
    for d in devices:
        if not d.get("ensure_normal_mode_on_startup", True):
            continue
        name = d.get("name") or f"rtu_{d.get('slave_id','?')}"
        sid = int(d.get("slave_id"))
        serial_cfg = {
            "baudrate": d.get("baudrate", 9600),
            "parity": d.get("parity", "N"),
            "stopbits": d.get("stopbits", 1),
            "bytesize": d.get("bytesize", 8),
            "timeout": d.get("timeout", 1.0),
        }

        resp = send_raw(sock, poller, service_name, driver_name, serial_cfg, Waveshare8CH.read_output_modes(sid), timeout_ms, print_debug, log_hex, log_fn)
        if resp:
            try:
                modes = Waveshare8CH.parse_registers(resp)
                if len(modes) == 8 and any(m != 0 for m in modes):
                    log_fn("warn", "non-normal modes detected -> set NORMAL(0)", {"device": name, "modes": modes})
                    _ = send_raw(sock, poller, service_name, driver_name, serial_cfg, Waveshare8CH.set_output_modes(sid, [0]*8), timeout_ms, print_debug, log_hex, log_fn)
            except Exception as e:
                log_fn("error", "ensure_normal_mode failed", {"device": name, "error": str(e)})

    # ----------------- main loop -----------------
    while True:
        # 1) poll DI/DO
        for d in devices:
            name = d.get("name") or f"rtu_{d.get('slave_id','?')}"
            sid = int(d.get("slave_id"))
            serial_cfg = {
                "baudrate": d.get("baudrate", 9600),
                "parity": d.get("parity", "N"),
                "stopbits": d.get("stopbits", 1),
                "bytesize": d.get("bytesize", 8),
                "timeout": d.get("timeout", 1.0),
            }

            di_resp = send_raw(sock, poller, service_name, driver_name, serial_cfg, Waveshare8CH.read_di(sid), timeout_ms, print_debug, log_hex, log_fn)
            do_resp = send_raw(sock, poller, service_name, driver_name, serial_cfg, Waveshare8CH.read_do(sid), timeout_ms, print_debug, log_hex, log_fn)

            try:
                di = Waveshare8CH.parse_bits(di_resp) if di_resp else last_di.get(name, [])
            except Exception as e:
                log_fn("warn", "DI parse failed (keep last)", {"device": name, "error": str(e)})
                di = last_di.get(name, [])

            try:
                do = Waveshare8CH.parse_bits(do_resp) if do_resp else last_do.get(name, [])
            except Exception as e:
                log_fn("warn", "DO parse failed (keep last)", {"device": name, "error": str(e)})
                do = last_do.get(name, [])

            last_di[name] = di
            last_do[name] = do

        # 2) report snapshot ตามรอบ
        if (time.monotonic() - last_report) >= report_interval:
            last_report = time.monotonic()

            # ส่งข้อมูลออกทีเดียวหลัง polling ครบ เป็นแพคเกจเดียว
            bundle = {}
            for dn in last_di.keys():
                key = dn.replace("_", "")  # io8ch_1 -> io8ch1
                di_bits = last_di.get(dn, []) or []
                do_bits = last_do.get(dn, []) or []
                dev = {}
                for i in range(8):
                    if i < len(do_bits):
                        dev[f"do{i+1}"] = bool(do_bits[i])
                    if i < len(di_bits):
                        dev[f"di{i+1}"] = bool(di_bits[i])
                bundle[key] = dev

            payload = {
                "type": "push_data",
                "source": service_name,
                "timestamp": iso_z(),
                "payload": bundle,
            }
            evt = make_event(service_name, integrator_name, "push_data", payload)
            sock.send_json(evt)
            p(f"[{service_name}] SNAPSHOT -> {integrator_name} {payload}")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
