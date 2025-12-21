from .formatter import format_log
from .db_writer import write_log

from shared.config_loader import config
from shared.zmq_helper.client import ZMQClient

class LoggerClient:
    def __init__(self, service_name):
        self.service_name = service_name
        self.log_service = config.get("LOG_SERVICE_NAME", "log-service")

        # best-effort sender (ผ่าน broker)
        self.zmq = ZMQClient(service_name=self.service_name)

    def _log(self, level, message, trace_id=None, extra=None):
        record = format_log(
            level=level,
            service=self.service_name,
            message=message,
            trace_id=trace_id,
            extra=extra,
        )

        # 1) local DB (reliable)
        write_log(record)

        # 2) send to log-service via broker (best effort)
        try:
            # ensure register once (simple safe approach)
            self.zmq.register()
        except Exception:
            pass

        try:
            self.zmq.send_request(
                dst=self.log_service,
                action="log",
                payload=record,
            )
        except Exception:
            pass

    def debug(self, msg, **kw): self._log("DEBUG", msg, **kw)
    def info(self, msg, **kw):  self._log("INFO", msg, **kw)
    def warn(self, msg, **kw):  self._log("WARN", msg, **kw)
    def error(self, msg, **kw): self._log("ERROR", msg, **kw)
