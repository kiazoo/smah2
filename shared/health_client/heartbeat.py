import threading
import time

class HeartbeatLoop:
    def __init__(self, send_func, interval=5):
        self.send_func = send_func
        self.interval = interval
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self.send_func()
            except Exception:
                pass
            time.sleep(self.interval)
