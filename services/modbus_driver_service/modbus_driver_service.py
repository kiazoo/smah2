import os
import time
import uuid
import yaml
import zmq
import serial
import threading
import queue
from zmq.utils import jsonapi

# NOTE: สำคัญมาก — ห้าม init LoggerClient ก่อน REGISTER OK
from shared.logger_client.client import LoggerClient


# ----------------- helpers -----------------
def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def load_config():
    base = os.path.dirname(__file__)
    with open(os.path.join(base, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def make_register(service_name: str) -> dict:
    # ✅ Variant A (probe ACK แล้ว)
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


def parse_hex_string(s: str) -> bytes:
    s = (s or "").strip().replace("0x", "").replace(",", " ").replace("\n", " ")
    parts = [p for p in s.split() if p]
    if not parts:
        return b""
    if len(parts) == 1 and len(parts[0]) % 2 == 0:
        return bytes.fromhex(parts[0])
    return bytes.fromhex("".join(parts))


def bytes_to_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def merge_serial_cfg(defaults: dict, incoming: dict) -> dict:
    out = dict(defaults or {})
    out.update(incoming or {})
    # normalize
    out["parity"] = str(out.get("parity", "N")).upper()
    out["baudrate"] = int(out.get("baudrate", 9600))
    out["stopbits"] = int(out.get("stopbits", 1))
    out["bytesize"] = int(out.get("bytesize", 8))
    out["timeout"] = float(out.get("timeout", 1.0))
    out["end_silence_ms"] = int(out.get("end_silence_ms", 50))
    out["max_rx_bytes"] = int(out.get("max_rx_bytes", 512))
    return out


def cfg_key(cfg: dict) -> tuple:
    # เปลี่ยนค่าพวกนี้ = reopen serial
    return (
        cfg.get("baudrate"),
        cfg.get("parity"),
        cfg.get("stopbits"),
        cfg.get("bytesize"),
        cfg.get("timeout"),
    )


def read_until_silence(ser: serial.Serial, overall_timeout_s: float, end_silence_ms: int, max_rx_bytes: int) -> bytes:
    rx = bytearray()
    t0 = time.monotonic()
    last_rx = None

    orig_timeout = ser.timeout
    ser.timeout = 0.02  # จับ gap เร็วๆ

    try:
        while True:
            now = time.monotonic()
            if (now - t0) >= overall_timeout_s:
                break
            if len(rx) >= max_rx_bytes:
                break

            waiting = getattr(ser, "in_waiting", 0) or 0
            n = min(waiting, max_rx_bytes - len(rx)) if waiting > 0 else 1
            chunk = ser.read(n)

            if chunk:
                rx.extend(chunk)
                last_rx = time.monotonic()
            else:
                if last_rx is not None and len(rx) > 0:
                    quiet_ms = (time.monotonic() - last_rx) * 1000.0
                    if quiet_ms >= end_silence_ms:
                        break
    finally:
        ser.timeout = orig_timeout

    return bytes(rx)


# ----------------- serial worker (1) + queue (2) -----------------
class SerialWorker(threading.Thread):
    """
    FIFO worker:
    - เปิด serial ค้าง
    - reopen เมื่อ cfg_key เปลี่ยน
    - อ่าน response ด้วย silence gap
    """

    def __init__(
        self,
        port: str,
        defaults: dict,
        job_q: queue.Queue,
        result_q: queue.Queue,
        log_fn,          # function(level, msg, extra)
        log_hex: bool,
        print_debug: bool,
    ):
        super().__init__(daemon=True)
        self.port = port
        self.defaults = defaults
        self.job_q = job_q
        self.result_q = result_q
        self.log_fn = log_fn
        self.log_hex = log_hex
        self.print_debug = print_debug

        self.stop_event = threading.Event()
        self.ser = None
        self.current_key = None

    def _p(self, *args):
        if self.print_debug:
            print(*args, flush=True)

    def _open(self, cfg: dict):
        self._p(f"[serial] open {self.port} cfg={cfg}")
        self.log_fn("info", "serial open", {"port": self.port, "cfg": cfg})

        self.ser = serial.Serial(
            port=self.port,
            baudrate=cfg["baudrate"],
            parity=cfg["parity"],
            stopbits=cfg["stopbits"],
            bytesize=cfg["bytesize"],
            timeout=cfg["timeout"],
        )
        self.current_key = cfg_key(cfg)
        time.sleep(0.05)

    def _close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.current_key = None

    def _ensure(self, cfg: dict):
        key = cfg_key(cfg)
        if (self.ser is None) or (self.current_key != key):
            self._close()
            self._open(cfg)

    def run(self):
        while not self.stop_event.is_set():
            try:
                job = self.job_q.get(timeout=0.2)
            except queue.Empty:
                continue

            req_id = job["req_id"]
            src = job["src"]
            action = job["action"]
            serial_cfg_in = job.get("serial_cfg") or {}
            tx = job.get("tx") or b""

            cfg = merge_serial_cfg(self.defaults, serial_cfg_in)

            try:
                self._ensure(cfg)

                try:
                    self.ser.reset_input_buffer()
                except Exception:
                    pass

                if self.log_hex:
                    self.log_fn("debug", "tx", {"req_id": req_id, "tx_hex": bytes_to_hex(tx), "serial": cfg})
                self._p(f"[serial] TX {bytes_to_hex(tx)}")

                t0 = time.monotonic()
                self.ser.write(tx)
                self.ser.flush()

                overall_timeout_s = max(0.2, cfg["timeout"] * 1.5)
                rx = read_until_silence(self.ser, overall_timeout_s, cfg["end_silence_ms"], cfg["max_rx_bytes"])
                rtt_ms = int((time.monotonic() - t0) * 1000)

                if self.log_hex:
                    self.log_fn("debug", "rx", {"req_id": req_id, "rx_hex": bytes_to_hex(rx), "rtt_ms": rtt_ms})
                self._p(f"[serial] RX {bytes_to_hex(rx)} rtt_ms={rtt_ms}")

                self.result_q.put({
                    "ok": True,
                    "req_id": req_id,
                    "src": src,
                    "action": action,
                    "payload": {
                        "status": "ok",
                        "hex": bytes_to_hex(rx),
                        "rx_len": len(rx),
                        "rtt_ms": rtt_ms,
                    }
                })

            except Exception as e:
                err = str(e)
                self.log_fn("error", "serial exchange error", {"req_id": req_id, "error": err})
                self._p(f"[serial] ERROR {err}")
                self.result_q.put({
                    "ok": False,
                    "req_id": req_id,
                    "src": src,
                    "action": action,
                    "payload": {"status": "error", "error": err},
                })

            finally:
                self.job_q.task_done()

        self._close()

    def stop(self):
        self.stop_event.set()


# ----------------- main driver -----------------
def main():
    cfg = load_config()

    service_name = (cfg.get("service") or {}).get("name", "modbus_driver_service")
    endpoint = (cfg.get("comm_core") or {}).get("endpoint", "tcp://127.0.0.1:5555")
    port = (cfg.get("serial") or {}).get("port", "/dev/ttyS0")
    defaults = ((cfg.get("serial") or {}).get("defaults") or {})

    driver_cfg = cfg.get("driver") or {}
    queue_max = int(driver_cfg.get("queue_max", 200))
    keepalive_sec = int(driver_cfg.get("keepalive_register_sec", 30))

    log_cfg = cfg.get("log") or {}
    log_level = str(log_cfg.get("level", "INFO")).upper()
    log_hex = bool(log_cfg.get("log_hex", False))
    print_debug = bool(log_cfg.get("print_debug", True))

    def p(*args):
        if print_debug:
            print(*args, flush=True)

    # ZMQ driver socket
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = service_name.encode("utf-8")
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(endpoint)

    poller = zmq.Poller()
    poller.register(sock, zmq.POLLIN)

    p(f"[{service_name}] connect broker={endpoint} port={port}")

    # ----------------- REGISTER (ก่อนใช้ LoggerClient) -----------------
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

    # ----------------- (4) LoggerClient หลัง REGISTER OK + ใช้ identity แยก -----------------
    # กัน identity ชนกับ driver socket: ใช้ชื่อ logger แยก
    logger_identity = f"{service_name}.logger"
    logger = LoggerClient(logger_identity)
    logger.level = log_level

    def log_fn(level: str, msg: str, extra: dict | None = None):
        extra = extra or {}
        # ใส่ service จริงไว้ทุก log เพื่อให้ trace ได้
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
            # กันพัง ถ้า log_service ยังไม่พร้อม
            pass

    p(f"[{service_name}] READY")
    log_fn("info", "driver ready", {"port": port, "broker": endpoint})

    # ----------------- (2) queues + worker -----------------
    job_q: queue.Queue = queue.Queue(maxsize=queue_max)
    result_q: queue.Queue = queue.Queue()

    worker = SerialWorker(
        port=port,
        defaults=defaults,
        job_q=job_q,
        result_q=result_q,
        log_fn=log_fn,
        log_hex=log_hex,
        print_debug=print_debug,
    )
    worker.start()

    # ----------------- (3) keepalive re-register -----------------
    last_keepalive = time.monotonic()

    def send_keepalive():
        reg = make_register(service_name)
        sock.send_json(reg)
        p(f"[{service_name}] KEEPALIVE REGISTER msg_id={reg['msg_id']}")
        log_fn("debug", "keepalive register", {"msg_id": reg["msg_id"]})

    # ----------------- main loop -----------------
    while True:
        # ส่งผลลัพธ์จาก worker กลับ client
        try:
            while True:
                r = result_q.get_nowait()
                resp = {
                    "msg_id": str(uuid.uuid4()),
                    "type": "response",
                    "src": service_name,
                    "dst": r["src"],
                    "action": r["action"],
                    "payload": r["payload"],
                    "correlation_id": r["req_id"],
                    "timestamp": utc_now(),
                }
                sock.send_json(resp)
                p(f"[{service_name}] OUT -> {resp}")
                result_q.task_done()
        except queue.Empty:
            pass

        # keepalive
        if (time.monotonic() - last_keepalive) >= keepalive_sec:
            send_keepalive()
            last_keepalive = time.monotonic()

        # รับข้อความจาก broker
        events = dict(poller.poll(200))
        if sock not in events:
            continue

        frames = sock.recv_multipart()
        msg = jsonapi.loads(frames[-1])
        p(f"[{service_name}] IN <- {msg}")

        if msg.get("type") != "request":
            continue

        src = msg.get("src")
        action = msg.get("action")
        req_id = msg.get("msg_id")
        payload = msg.get("payload") or {}

        # ping
        if action == "ping":
            resp = {
                "msg_id": str(uuid.uuid4()),
                "type": "response",
                "src": service_name,
                "dst": src,
                "action": "ping",
                "payload": {"status": "ok", "service": service_name, "ts": utc_now()},
                "correlation_id": req_id,
                "timestamp": utc_now(),
            }
            sock.send_json(resp)
            p(f"[{service_name}] OUT -> {resp}")
            continue

        # modbus.send_raw (raw hex in/out, no decode)
        if action == "modbus.send_raw":
            serial_cfg = payload.get("serial") or {}
            hex_cmd = payload.get("hex") or ""

            try:
                tx = parse_hex_string(hex_cmd)
                if not tx:
                    raise ValueError("hex is empty")

                try:
                    job_q.put_nowait({
                        "req_id": req_id,
                        "src": src,
                        "action": "modbus.send_raw",
                        "serial_cfg": serial_cfg,
                        "tx": tx,
                    })
                    log_fn("debug", "enqueue modbus.send_raw", {"req_id": req_id, "from": src, "tx_hex": bytes_to_hex(tx)})
                except queue.Full:
                    resp = {
                        "msg_id": str(uuid.uuid4()),
                        "type": "response",
                        "src": service_name,
                        "dst": src,
                        "action": "modbus.send_raw",
                        "payload": {"status": "error", "error": "driver queue full"},
                        "correlation_id": req_id,
                        "timestamp": utc_now(),
                    }
                    sock.send_json(resp)

            except Exception as e:
                resp = {
                    "msg_id": str(uuid.uuid4()),
                    "type": "response",
                    "src": service_name,
                    "dst": src,
                    "action": "modbus.send_raw",
                    "payload": {"status": "error", "error": str(e)},
                    "correlation_id": req_id,
                    "timestamp": utc_now(),
                }
                sock.send_json(resp)

            continue

        # unknown
        resp = {
            "msg_id": str(uuid.uuid4()),
            "type": "response",
            "src": service_name,
            "dst": src,
            "action": action,
            "payload": {"status": "error", "error": f"unknown action: {action}"},
            "correlation_id": req_id,
            "timestamp": utc_now(),
        }
        sock.send_json(resp)


if __name__ == "__main__":
    main()
