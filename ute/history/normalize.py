"""Validate measured quarter-hours; never interpolate absent readings."""
from datetime import date, datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Montevideo")
ACTIVE_LABEL = "Energia Activa Entrante kWh"
INTERVAL = timedelta(minutes=15)
INTERVAL_MS = 900_000


def is_number(value) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))


def normalize_quarters(payload: dict, first: date, last: date,
                       now: datetime = None) -> dict[str, float]:
    """Return completed measurements keyed by interval start in UTC.

    UTE's data_array uses Unix milliseconds and measured interval energy in kWh.
    Dates in the query refer to Montevideo; null values represent missing data.
    """
    datasets = [series for series in payload["CURVA_DE_CONSUMO"]["data_array"]
                if series.get("label") == ACTIVE_LABEL]
    if len(datasets) != 1:
        raise ValueError("Expected exactly one incoming active energy series")
    now = now or datetime.now(timezone.utc)
    result = {}
    for stamp, value in datasets[0]["data"]:
        if not is_number(stamp) or stamp % INTERVAL_MS:
            raise ValueError("Invalid UTE interval timestamp")
        start = datetime.fromtimestamp(stamp / 1000, timezone.utc)
        if not first <= start.astimezone(TZ).date() <= last:
            raise ValueError("UTE interval outside requested date range")
        if value is None or start + INTERVAL > now:
            continue
        if not is_number(value) or value < 0:
            raise ValueError("Invalid UTE energy reading")
        key = start.isoformat()
        if key in result and result[key] != value:
            raise ValueError("Conflicting duplicate UTE intervals")
        result[key] = float(value)
    return result
