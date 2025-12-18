import threading

from .providers.env import load_from_env
from .providers.db import load_from_db
from .providers.file import load_from_file


class ConfigLoader:
    _lock = threading.Lock()

    def __init__(self):
        self._data = {}
        self.reload()

    def reload(self):
        with self._lock:
            data = {}

            # priority: low → high
            data.update(load_from_file())
            data.update(load_from_db())
            data.update(load_from_env())

            self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def all(self):
        return dict(self._data)


# singleton
config = ConfigLoader()
