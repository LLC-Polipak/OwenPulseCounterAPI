import logging
from datetime import datetime
from typing import Any

from serial import Serial

from app.api.common import SensorReading
from app.api.config import configure_logging
from app.owen_counter.owen_ci8 import OwenCI8

configure_logging()
logger = logging.getLogger(__name__)


class Sensor:
    reading: SensorReading

    def __init__(
        self,
        name: str,
        device: OwenCI8,
        parameter_hash: bytes,
        serial: Serial,
    ):
        self.name = name
        self.device = device
        self.parameter_hash = parameter_hash
        self.serial = serial
        self.reading = SensorReading()
        # reading_time: datetime = datetime.now()

    def update(self) -> None:
        try:
            self.reading.value = self.device.read_parameter(
                self.serial, self.parameter_hash
            )
            self.reading.time = datetime.now()
        except TimeoutError:
            logger.error(f'Сенсор {self.name} не ответил')
        except Exception as err:
            logger.error(f'Сенсор {self.name} {err}')

    def get(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'reading': self.reading.value,
            'reading_time': self.reading.time,
        }
