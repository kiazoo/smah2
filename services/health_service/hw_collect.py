import os
import glob
import time
import json
import shutil


# -------- System --------
def meminfo():
    mem = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                k, v = line.split(":")
                mem[k.strip()] = int(v.strip().split()[0])  # kB
    except Exception:
        return {"total_kb": None, "available_kb": None, "used_kb": None}

    total = mem.get("MemTotal")
    avail = mem.get("MemAvailable")
    used = None
    if total is not None and avail is not None:
        used = max(total - avail, 0)
    return {"total_kb": total, "available_kb": avail, "used_kb": used}


def disk_usage(path="/"):
    try:
        du = shutil.disk_usage(path)
        return {"total": du.total, "used": du.used, "free": du.free}
    except Exception:
        return {"total": None, "used": None, "free": None}


def loadavg():
    try:
        l1, l5, l15 = os.getloadavg()
        return {"1m": l1, "5m": l5, "15m": l15}
    except Exception:
        return {"1m": None, "5m": None, "15m": None}


# -------- Thermal --------
def thermal_zones():
    zones = []
    for p in glob.glob("/sys/class/thermal/thermal_zone*"):
        try:
            with open(f"{p}/type", "r") as f:
                ztype = f.read().strip()
            with open(f"{p}/temp", "r") as f:
                temp_c = int(f.read().strip()) / 1000.0
            zones.append({"zone": p.split("/")[-1], "type": ztype, "temp_c": temp_c})
        except Exception:
            continue
    return zones


# -------- NPU Rockchip (best-effort) --------
def _read_int(path):
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None


def npu_rockchip():
    candidates = [
        "/sys/kernel/debug/rknpu",
        "/sys/kernel/debug/npu",
    ]

    base = None
    for c in candidates:
        if os.path.exists(c):
            base = c
            break

    if not base:
        hits = glob.glob("/sys/kernel/debug/*npu*")
        if hits:
            base = hits[0]

    if not base or not os.path.exists(base):
        return {"status": "unavailable", "reason": "npu debug path not found"}

    usage = None
    for name in ("load", "usage", "utilization"):
        v = _read_int(os.path.join(base, name))
        if v is not None:
            usage = v
            break

    mem = None
    for name in ("mem", "memory", "mem_used"):
        v = _read_int(os.path.join(base, name))
        if v is not None:
            mem = v
            break

    return {
        "status": "ok",
        "driver": "rockchip-npu",
        "base_path": base,
        "usage": usage,
        "memory": mem,
        "error": None,
    }


def collect_hw_snapshot():
    return {
        "ts": int(time.time()),
        "system": {
            "memory": meminfo(),
            "disk": disk_usage("/"),
            "load": loadavg(),
        },
        "thermal": thermal_zones(),
        "npu": npu_rockchip(),
    }


if __name__ == "__main__":
    print(json.dumps(collect_hw_snapshot(), indent=2))
