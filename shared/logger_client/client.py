from .formatter import format_log
from .db_writer import write_log
from .zmq_publisher import publish_log

class LoggerClient:
    def __init__(self, service_name):
        self.service_name = service_name

    def _log(self, level, message, trace_id=None, extra=None):
        record = format_log(
            level=level,
            service=self.service_name,
            message=message,
            trace_id=trace_id,
            extra=extra,
        )

        # 1) write local DB (reliable)
        write_log(record)

        # 2) publish via ZMQ (best effort)
        try:
            publish_log(record)
        except Exception:
            pass

    def debug(self, msg, **kw): self._log("DEBUG", msg, **kw)
    def info(self, msg, **kw):  self._log("INFO", msg, **kw)
    def warn(self, msg, **kw):  self._log("WARN", msg, **kw)
    def error(self, msg, **kw): self._log("ERROR", msg, **kw)
