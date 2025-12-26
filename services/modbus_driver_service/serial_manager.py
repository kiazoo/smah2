import serial
import threading
import time


class SerialManager:
    def __init__(self, port, logger=None):
        self.port = port
        self.logger = logger
        self.lock = threading.Lock()
        self.ser = None
        self.current_cfg = None

    def _open(self, cfg):
        if self.logger:
            self.logger.info("open serial", extra={"port": self.port, "cfg": cfg})

        self.ser = serial.Serial(
            port=self.port,
            baudrate=cfg["baudrate"],
            parity=cfg.get("parity", "N"),
            stopbits=cfg.get("stopbits", 1),
            bytesize=cfg.get("bytesize", 8),
            timeout=cfg.get("timeout", 1.0),
        )
        self.current_cfg = cfg.copy()
        time.sleep(0.05)

    def _close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.current_cfg = None

    def _cfg_changed(self, cfg):
        if not self.current_cfg:
            return True
        for k in ["baudrate", "parity", "stopbits", "bytesize", "timeout"]:
            if self.current_cfg.get(k) != cfg.get(k):
                return True
        return False

    def _read_until_silence(self, overall_timeout_s: float, end_silence_ms: int, max_bytes: int) -> bytes:
        """
        Read until no new bytes arrive for end_silence_ms, or overall timeout reached.
        (RTU framing style)
        """
        buf = bytearray()
        t0 = time.monotonic()
        last_rx = None

        # make serial timeout short to detect gap quickly
        orig_timeout = self.ser.timeout
        self.ser.timeout = 0.02

        try:
            while True:
                now = time.monotonic()
                if (now - t0) >= overall_timeout_s:
                    break
                if len(buf) >= max_bytes:
                    break

                waiting = getattr(self.ser, "in_waiting", 0) or 0
                n = min(waiting, max_bytes - len(buf)) if waiting > 0 else 1
                chunk = self.ser.read(n)

                if chunk:
                    buf.extend(chunk)
                    last_rx = time.monotonic()
                else:
                    if last_rx is not None:
                        quiet_ms = (time.monotonic() - last_rx) * 1000.0
                        if quiet_ms >= end_silence_ms:
                            break
        finally:
            self.ser.timeout = orig_timeout

        return bytes(buf)

    def send_raw(self, cfg, data: bytes) -> bytes:
        """
        cfg keys expected:
          baudrate, parity, stopbits, bytesize, timeout (seconds)
        optional:
          end_silence_ms (default 50)
          max_rx_bytes (default 512)
        """
        end_silence_ms = int(cfg.get("end_silence_ms", 50))
        max_rx_bytes = int(cfg.get("max_rx_bytes", 512))
        overall_timeout_s = float(cfg.get("timeout", 1.0))

        with self.lock:
            if not self.ser or self._cfg_changed(cfg):
                self._close()
                self._open(cfg)

            # clean input before tx
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass

            self.ser.write(data)
            self.ser.flush()

            # read until silence
            return self._read_until_silence(overall_timeout_s, end_silence_ms, max_rx_bytes)
