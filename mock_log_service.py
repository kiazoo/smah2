import time
import random
from datetime import datetime

from shared.logger_client.client import LoggerClient

SERVICE_NAME = "mock-worker"

def main():
    logger = LoggerClient(service_name=SERVICE_NAME)

    levels = ["debug", "info", "warn", "error"]

    i = 0
    while True:
        level = random.choice(levels)
        msg = f"test log message #{i}"

        extra = {
            "counter": i,
            "random": random.randint(1, 100),
            "time": datetime.utcnow().isoformat()
        }

        if level == "debug":
            logger.debug(msg, extra=extra)
        elif level == "info":
            logger.info(msg, extra=extra)
        elif level == "warn":
            logger.warn(msg, extra=extra)
        elif level == "error":
            logger.error(msg, extra=extra)

        print(f"[{SERVICE_NAME}] send {level.upper()} : {msg}")

        i += 1
        time.sleep(1)   # ยิงทุก 1 วินาที

if __name__ == "__main__":
    main()
