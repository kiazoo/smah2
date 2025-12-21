from datetime import datetime
from copy import deepcopy


class Aggregator:
    """
    Aggregates incoming service payloads per uplink.

    - แยก bucket ตาม uplink_name
    - ส่งเฉพาะข้อมูลที่มี update ใหม่
    - ใส่ device_id + timestamp ทุกครั้ง
    """

    def __init__(self, device_id: str):
        self.device_id = device_id

        # uplink_name -> services payload
        self._services = {}

        # uplink_name -> last sent health snapshot
        self._last_health = {}

    # ---------- PUSH DATA ----------

    def push(self, uplink_name: str, payload: dict):
        """
        รับ payload จาก service (ผ่าน handler)
        payload format:
        {
            "service": "sensor_1",
            "data": {...}
        }
        """
        if not payload:
            return

        service = payload.get("service")
        data = payload.get("data")

        if not service or data is None:
            return

        if uplink_name not in self._services:
            self._services[uplink_name] = {}

        # overwrite latest state per service
        self._services[uplink_name][service] = data

    # ---------- BUILD PAYLOAD ----------

    def build(self, uplink_name: str, health_snapshot: dict | None):
        """
        Build uplink payload.
        Return None if nothing new to send.
        """

        services = self._services.get(uplink_name)
        last_health = self._last_health.get(uplink_name)

        services_changed = bool(services)
        health_changed = health_snapshot != last_health

        # ไม่มีอะไรใหม่จริง ๆ → ไม่ส่ง
        if not services_changed and not health_changed:
            return None

        payload = {
            "device_id": self.device_id,
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "services": deepcopy(services) if services else {},
            "health": deepcopy(health_snapshot) if health_snapshot else None,
        }

        return payload

    # ---------- CLEAR AFTER SEND ----------

    def clear(self, uplink_name: str):
        """
        Clear sent services bucket for uplink.
        Health จะถูกจำไว้เพื่อเทียบรอบถัดไป
        """
        if uplink_name in self._services:
            self._services[uplink_name].clear()

    # ---------- HEALTH TRACKING ----------

    def mark_health_sent(self, uplink_name: str, health_snapshot: dict | None):
        """
        Mark health snapshot as sent
        """
        self._last_health[uplink_name] = deepcopy(health_snapshot)

    # ---------- DEBUG / INTROSPECTION ----------

    def has_pending(self, uplink_name: str) -> bool:
        return bool(self._services.get(uplink_name))

    def dump_state(self) -> dict:
        return {
            "services": deepcopy(self._services),
            "last_health": deepcopy(self._last_health),
        }
