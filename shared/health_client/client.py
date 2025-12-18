from shared.zmq_helper.client import ZMQClient
from shared.config_loader import config
from shared.logger_client import logger

from .status import HealthState, HealthStatus
from .heartbeat import HeartbeatLoop


class HealthClient:
    def __init__(self):
        self.service_name = config.get("SERVICE_NAME", "unknown")
        self.health_service = config.get("HEALTH_SERVICE_NAME", "health-service")

        self.state = HealthState()
        self.client = ZMQClient(service_name=self.service_name)
        self.hb = HeartbeatLoop(self._send_heartbeat)

    def start(self):
        logger.info("health_client started")
        self.client.register()
        self.hb.start()

    def stop(self):
        self.set_status(HealthStatus.STOPPED)
        self.hb.stop()

    def set_status(self, status: HealthStatus):
        self.state.status = status
        logger.info("health status updated", extra={"status": status})

    def _send_heartbeat(self):
        payload = {
            "status": self.state.status,
            "uptime": self.state.uptime(),
        }

        self.client.send_request(
            dst=self.health_service,
            action="heartbeat",
            payload=payload,
        )
