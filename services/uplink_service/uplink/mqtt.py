import json
import paho.mqtt.client as mqtt
from .base import UplinkBase

class MqttUplink(UplinkBase):
    def __init__(self, name: str, host: str, port: int, topic: str, username: str = "", password: str = "", qos: int = 1):
        super().__init__(name)
        self.host = host
        self.port = int(port)
        self.topic = topic
        self.qos = int(qos)

        self.client = mqtt.Client(client_id=f"{name}-uplink", clean_session=True)
        if username or password:
            self.client.username_pw_set(username, password)

        self._connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = (rc == 0)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False

    def send(self, payload: dict) -> None:
        if not self._connected:
            raise RuntimeError("MQTT not connected")

        data = json.dumps(payload, ensure_ascii=False)
        info = self.client.publish(self.topic, data, qos=self.qos)
        info.wait_for_publish()
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed rc={info.rc}")
