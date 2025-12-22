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

    def send_raw(self, cfg, data: bytes) -> bytes:
        with self.lock:
            if not self.ser or self._cfg_changed(cfg):
                self._close()
                self._open(cfg)

            self.ser.reset_input_buffer()
            self.ser.write(data)
            self.ser.flush()

            return self.ser.read(256)
