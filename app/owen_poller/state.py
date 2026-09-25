from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


@dataclass
class SensorRuntimeState:
    """
    Состояние сенсора в режиме реального времени.
    Собирает метрики успешности опросов и данные для формирования минутных срезов.
    """

    last_value: float | int | None = None
    last_ts: datetime | None = None

    current_minute: datetime | None = None
    minute_start_value: float | int | None = None
    minute_end_value: float | int | None = None

    attempt_count: int = 0
    success_count: int = 0

    last_success_ts: datetime | None = None

    last_minute_snapshot: Optional['SensorMinuteSnapshot'] = None


@dataclass
class SensorMinuteSnapshot:
    """
    Фиксированный "снимок" состояния сенсора по окончании минуты.
    Используется для отправки исторической отчетности.
    """

    minute: datetime

    value: float | int | None
    status: Literal['OK', 'STOP', 'UNKNOWN']

    success_rate: float
    last_seen_at: datetime | None
