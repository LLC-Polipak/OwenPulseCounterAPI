from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class SensorReading:
    value: Any = None
    time: datetime = datetime.now()


@dataclass
class SensorRuntimeState:
    last_value: int | None = None
    last_ts: datetime | None = None

    current_minute: datetime | None = None
    current_minute_total: int = 0

    last_minute_ts: datetime | None = None
    last_minute_total: int = 0

    last_success_ts: datetime | None = None
