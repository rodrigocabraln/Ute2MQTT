#!/usr/bin/env python3
"""Fetch measured quarter-hours independently of the billing API."""
import argparse
from datetime import date, datetime, timedelta
import logging
import os
import threading
import signal

from ute.credentials import CredentialsManager
from ute.history.normalize import TZ
from ute.history.portal import fetch
from ute.history.publish import publish_history
from ute.history.store import IntervalStore
from ute.mqtt import MQTTPublisher

LOGGER = logging.getLogger(__name__)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing {name}")
    return value


def synchronize(first: date, last: date) -> int:
    service_id = required("UTE_SERVICE_ID")
    point_id = required("UTE_SERVICE_POINT_ID")
    credentials = CredentialsManager(os.environ.get("CREDENTIALS_PATH", "./credentials")).get_user_credentials()
    if not credentials:
        raise ValueError("Run setup.py to save encrypted portal credentials")
    intervals = fetch(
        {"document": credentials["username"], "password": credentials["password"]},
        {"serviceAgreementId": service_id, "servicePointId": point_id}, first, last,
    )
    store = IntervalStore(os.environ.get("UTE_HISTORY_DB", "./data/history.sqlite3"), point_id)
    store.merge(intervals)  # save before MQTT; the next run can retry publication
    publisher = MQTTPublisher(
        broker=required("MQTT_BROKER"), port=int(os.environ.get("MQTT_PORT", "1883")),
        username=os.environ.get("MQTT_USERNAME"), password=os.environ.get("MQTT_PASSWORD"),
        topic_prefix=os.environ.get("MQTT_TOPIC_PREFIX", "UTE"),
        discovery_prefix=os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant"),
    )
    try:
        if not publisher.connect():
            raise RuntimeError("Could not connect to MQTT broker")
        publish_history(publisher, service_id, store.read())
    finally:
        publisher.disconnect()
    LOGGER.info("Synchronized %d measured quarter-hours", len(intervals))
    return len(intervals)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Synchronize once and exit")
    parser.add_argument("--start", type=date.fromisoformat, help="Initial backfill date, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="Last date, YYYY-MM-DD")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if (args.start or args.end) and not args.once:
        parser.error("Explicit dates require --once")
    lookback = int(os.environ.get("UTE_HISTORY_LOOKBACK_DAYS", "30"))
    poll_hours = float(os.environ.get("UTE_HISTORY_POLL_HOURS", "6"))
    if lookback < 1 or not 0 < poll_hours < float("inf"):
        parser.error("Lookback and polling interval must be positive and finite")
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        last = args.end or datetime.now(TZ).date()
        first = args.start or last - timedelta(days=lookback - 1)
        if first > last:
            parser.error("Start must precede end")
        try:
            synchronize(first, last)
        except Exception as error:
            # Do not log HTTP bodies, credentials or exception URLs.
            LOGGER.error("History synchronization failed (%s)", type(error).__name__)
            if args.once:
                return 1
        if args.once:
            return 0
        stop.wait(poll_hours * 3600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
