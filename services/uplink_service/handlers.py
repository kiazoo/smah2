def handle_push_data(aggregator, payload: dict) -> dict:
    print("[handler] called payload =", payload, flush=True)

    if not isinstance(payload, dict):
        return {"ok": False, "error": "payload not dict"}

    source = payload.get("source")
    data = payload.get("data")

    if not source or not isinstance(data, dict):
        return {
            "ok": False,
            "error": "invalid push_data schema",
            "payload": payload,
        }

    aggregator.update_service_data(source, data)
    return {"ok": True}
