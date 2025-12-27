import os
import yaml
import time
from typing import Dict


class ConfigManager:
    def __init__(self, path: str):
        self.path = path
        self._mtime = 0
        self.cfg = {}

    def write(self, cfg: dict):
        """
        Write config to file and update internal state
        """
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)

        # update internal state
        self.cfg = cfg
        self._mtime = os.path.getmtime(self.path)


    def load(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def reload_if_changed(self) -> bool:
        try:
            mtime = os.path.getmtime(self.path)
        except FileNotFoundError:
            return False

        if mtime == self._mtime:
            return False

        self._mtime = mtime
        self.cfg = self.load()
        print("[uplink_service] config reloaded", flush=True)
        return True

    def get_uplinks_cfg(self):
        return self.cfg.get("uplinks", [])
