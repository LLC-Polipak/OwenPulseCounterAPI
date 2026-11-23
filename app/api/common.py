"""Общие структуры данных и утилиты."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SensorReading:
    """Данные одного измерения сенсора."""

    value: Any = None
    time: datetime = field(default_factory=datetime.now)
