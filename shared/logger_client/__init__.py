from .client import LoggerClient
from shared.config_loader import config

logger = LoggerClient(
    service_name=config.get("SERVICE_NAME", "unknown")
)
