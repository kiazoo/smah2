from typing import Dict
import yaml


def handle_push_data(aggregator, msg: dict, uplink_name: str):
    print("[DEBUG][handler] msg =", msg, flush=True)

    source = msg.get("source")
    data = msg.get("payload")

    print("[DEBUG][handler] source =", source, flush=True)
    print("[DEBUG][handler] payload keys =", list(data.keys()) if isinstance(data, dict) else data, flush=True)

    if not source or not isinstance(data, dict):
        print("[DEBUG][handler] INVALID schema", flush=True)
        return
    
    aggregator.update(
        uplink_name=uplink_name,
        source=source,
        data=data,
    )


def handle_update_uplink_config(config_path: str, cfg_mgr, msg: Dict):
    """
    RPC payload:
    {
      "payload": {
        "uplinks": [
          { "name": "...", "enabled": true, "interval_sec": 10 }
        ]
      }
    }
    """
    if not isinstance(msg, dict):
        return False, "invalid msg"

    payload = msg.get("payload")
    if not isinstance(payload, dict):
        return False, "missing payload"

    uplinks = payload.get("uplinks")
    if not isinstance(uplinks, list):
        return False, "payload.uplinks must be list"

    cfg = cfg_mgr.cfg or {}
    cfg.setdefault("uplinks", [])

    uplinks_cfg = cfg["uplinks"]
    uplinks_map = {u["name"]: u for u in uplinks_cfg if "name" in u}

    for u in uplinks:
        name = u.get("name")
        if not name:
            continue

        if name in uplinks_map:
            uplinks_map[name].update(u)
        else:
            uplinks_cfg.append(u)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    return True, "config updated"
