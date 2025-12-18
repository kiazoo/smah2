import json
from pathlib import Path

CONFIG_FILES = [
    "config.json",
    "config.yaml",
]

def load_from_file():
    for path in CONFIG_FILES:
        p = Path(path)
        if p.exists():
            if p.suffix == ".json":
                return json.loads(p.read_text())
    return {}
