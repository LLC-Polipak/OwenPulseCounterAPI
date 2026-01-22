from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class SensorReading:
    value: Any = None
    time: datetime = datetime.now()
