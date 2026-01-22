from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


@dataclass
class SensorRuntimeState:
    last_value: int | None = None
    last_ts: datetime | None = None

    current_minute: datetime | None = None
    minute_start_value: int | None = None
    minute_end_value: int | None = None

    attempt_count: int = 0
    success_count: int = 0

    last_success_ts: datetime | None = None

    last_minute_snapshot: Optional['SensorMinuteSnapshot'] = None


@dataclass
class SensorMinuteSnapshot:
    minute: datetime

    value: int | None
    status: Literal['OK', 'STOP', 'UNKNOWN']

    success_rate: float
    last_seen_at: datetime | None
