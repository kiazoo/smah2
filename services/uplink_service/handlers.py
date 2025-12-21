import yaml
from typing import Dict, Tuple


# =========================================================
# PUSH DATA HANDLER
# =========================================================

def handle_push_data(aggregator, payload: dict, uplink_name: str):
    """
    payload schema ที่รองรับ:
    {
        "source": "sensor_1",
        "data": {...}
    }
    """

    if not payload or not isinstance(payload, dict):
        return

    source = payload.get("source")
    data = payload.get("data")

    if not source or not isinstance(data, dict):
        return

    # ✅ ใช้ push เท่านั้น (Aggregator ไม่มี update)
    aggregator.push(
        uplink_name=uplink_name,
        payload={
            "service": source,
            "data": data,
        }
    )


# =========================================================
# UPDATE UPLINK CONFIG HANDLER
# =========================================================

def handle_update_uplink_config(
    config_path: str,
    cfg_mgr,
    payload: Dict
) -> Tuple[bool, str]:
    """
    payload:
    {
        "uplinks": [
            { "name": "...", "enabled": true, "interval_sec": 10 }
        ]
    }
    """

    if not payload or "uplinks" not in payload:
        return False, "invalid payload"

    new_uplinks = payload["uplinks"]
    if not isinstance(new_uplinks, list):
        return False, "uplinks must be list"

    cfg = cfg_mgr.cfg or {}
    cfg.setdefault("uplinks", [])

    uplinks_cfg = cfg["uplinks"]

    uplinks_map = {
        u.get("name"): u
        for u in uplinks_cfg
        if isinstance(u, dict) and u.get("name")
    }

    for u in new_uplinks:
        name = u.get("name")
        if not name:
            continue

        if name in uplinks_map:
            uplinks_map[name].update(u)
        else:
            uplinks_cfg.append(u)

    try:
        cfg_mgr.write(cfg)
        return True, "config updated"
    except Exception as e:
        return False, f"write config failed: {e}"
