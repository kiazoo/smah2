from datetime import datetime
import uuid

def format_log(level, service, message, trace_id=None, extra=None):
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "service": service,
        "message": message,
        "trace_id": trace_id or str(uuid.uuid4()),
        "extra": extra or {},
    }
