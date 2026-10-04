"""MQTT history contract and Home Assistant discovery.

Historical timestamps are carried in payloads. MQTT sensors alone cannot backfill
Home Assistant recorder; consumers must import historical statistics explicitly.
"""
from datetime import datetime, timezone
import json


def publish_json(client, topic: str, payload: dict) -> None:
    result = client.publish(topic, json.dumps(payload, allow_nan=False), qos=1, retain=True)
    result.wait_for_publish(timeout=15)
    if result.rc != 0 or not result.is_published():
        raise RuntimeError("MQTT publication was not acknowledged")


def publish_history(publisher, service_id: str, intervals: dict[str, float]) -> None:
    if not intervals:
        return  # absence must not overwrite the last measured value with zero
    base = f"{publisher.topic_prefix}/{service_id}/history"
    days = {}
    for stamp, value in sorted(intervals.items()):
        utc_day = stamp[:10]
        days.setdefault(utc_day, {})[stamp] = value
    # Small retained daily chunks avoid an ever-growing single MQTT message.
    for day, values in days.items():
        publish_json(publisher.client, f"{base}/days/{day}", {
            "schema_version": 1, "timezone": "America/Montevideo",
            "interval_minutes": 15, "intervals": values,
        })
    latest = max(intervals)
    publish_json(publisher.client, f"{base}/state", {
        "latest_start": latest, "latest_kwh": intervals[latest],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    publish_json(publisher.client, f"{base}/index", {
        "schema_version": 1, "days": sorted(days), "day_partition_timezone": "UTC",
    })
    unique_id = f"ute_{service_id}_quarter_hour"
    publish_json(publisher.client,
        f"{publisher.discovery_prefix}/sensor/{unique_id}/config", {
            "name": "Consumo último intervalo de 15 minutos", "unique_id": unique_id,
            "state_topic": f"{base}/state", "value_template": "{{ value_json.latest_kwh }}",
            "json_attributes_topic": f"{base}/state", "unit_of_measurement": "kWh",
            "device_class": "energy", "state_class": "measurement",
            "device": {"identifiers": [f"ute_{service_id}"], "name": f"UTE {service_id}"},
        })
