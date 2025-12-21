import time
import random
from shared.zmq_helper.client import ZMQClient

def main():
    c = ZMQClient(service_name="mock-sender")
    c.register()

    i = 0
    while True:
        payload = {
            "source": "mock-sensor",
            "data": {
                "counter": i,
                "value": round(random.uniform(20, 40), 2)
            }
        }

        resp = c.send_request(
            dst="uplink_service",
            action="push_data",
            payload=payload
        )
        print("push_data resp:", resp)

        i += 1
        time.sleep(3)

if __name__ == "__main__":
    main()
