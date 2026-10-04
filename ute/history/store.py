"""Durable, idempotent storage; revised UTE readings replace previous values."""
from pathlib import Path
import sqlite3


class IntervalStore:
    def __init__(self, path: str, service_point_id: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.service_point_id = service_point_id
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS intervals (
                service_point TEXT NOT NULL, start TEXT NOT NULL,
                kwh REAL NOT NULL CHECK(kwh >= 0),
                PRIMARY KEY(service_point, start))""")

    def merge(self, intervals: dict[str, float]) -> None:
        with sqlite3.connect(self.path) as db:
            db.executemany(
                "INSERT INTO intervals VALUES (?, ?, ?) "
                "ON CONFLICT(service_point, start) DO UPDATE SET kwh=excluded.kwh",
                [(self.service_point_id, stamp, value) for stamp, value in intervals.items()],
            )

    def read(self) -> dict[str, float]:
        with sqlite3.connect(self.path) as db:
            return dict(db.execute(
                "SELECT start, kwh FROM intervals WHERE service_point=? ORDER BY start",
                (self.service_point_id,),
            ))
