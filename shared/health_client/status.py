from enum import Enum
import time

class HealthStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


class HealthState:
    def __init__(self):
        self.status = HealthStatus.STARTING
        self.start_time = time.time()

    def uptime(self):
        return int(time.time() - self.start_time)
