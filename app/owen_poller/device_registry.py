import copy
import logging
from datetime import datetime
from typing import Any

from app.api.common import SensorReading
from app.owen_poller.enums import SensorStatus
from app.owen_poller.exceptions import DeviceNotFound
from app.owen_poller.sensor import Sensor

logger = logging.getLogger(__name__)


class DeviceRegistry:
    """Реестр устройств. Хранит, сортирует сенсоры и подготавливает данные для API."""

    def __init__(self):
        self.sensors: dict[str, Sensor] = {}
        self.last_readings: dict[str, SensorReading] = {}

    def add_sensor(self, sensor: Sensor) -> None:
        """Добавляет сенсор в реестр."""
        self.sensors[sensor.name] = sensor

    def get_sensor_readings(self, sensor_name: str) -> dict[str, Any]:
        """Возвращает сырые показания одного логического сенсора."""
        if sensor_name not in self.sensors:
            raise DeviceNotFound(sensor_name)
        return self.sensors[sensor_name].get()

    def get_sorted_sensors(self) -> list[Sensor]:
        """Возвращает список сенсоров, отсортированный по их приоритету (poll_priority)."""
        return sorted(self.sensors.values(), key=lambda s: s.device.poll_priority)

    def get_list_readings(self, work_centers: list[str]) -> list[dict[str, Any]]:
        """Бизнес-логика формирования ответов для внешнего API (с расчетом скорости)."""
        for_sent = []
        measured_at = datetime.now()
        for work_center in work_centers:
            response = {
                'sensor': work_center,
                'value': None,
                'measured_at': measured_at,
                'status': SensorStatus.NOT_FOUND,
            }

            if not (sensor := self.sensors.get(work_center)):
                for_sent.append(response)
                continue

            current_reading = sensor.reading
            if current_reading.value is None:
                response['status'] = SensorStatus.OFFLINE
                for_sent.append(response)
                continue

            previous_reading = self.last_readings.get(sensor.name)

            if previous_reading is None or previous_reading.value is None:
                duration = 0.0
                prev_val = current_reading.value
                self.last_readings[sensor.name] = copy.copy(current_reading)
            else:
                duration = (
                    current_reading.time - previous_reading.time
                ).total_seconds()
                prev_val = previous_reading.value

            if duration <= 0 and previous_reading is not None:
                duration = 0.0
                prev_val = current_reading.value

            metric = sensor.device.calculate_instant_metric(
                current_reading.value, prev_val, duration
            )

            response['value'] = metric
            response['status'] = sensor.device.get_status(metric, sensor.state)

            for_sent.append(response)

            if duration > 0:
                self.last_readings[sensor.name] = copy.copy(current_reading)

        return for_sent

    def get_minute_state(self, sensors_list: list[str]) -> list[dict]:
        """Формирует отчет о минутном состоянии сенсоров."""
        result = []
        for name in sensors_list:
            if name not in self.sensors:
                result.append(
                    {
                        'sensor': name,
                        'status': SensorStatus.NOT_FOUND,
                        'value': None,
                        'measured_at': None,
                        'changed_at': None,
                        'success_rate': 0.0,
                    }
                )
                continue

            snapshot = self.sensors[name].state.last_minute_snapshot
            if not snapshot or snapshot.minute is None:
                continue

            result.append(
                {
                    'sensor': name,
                    'status': snapshot.status,
                    'value': snapshot.value,
                    'measured_at': snapshot.minute,
                    'changed_at': snapshot.last_seen_at,
                    'success_rate': snapshot.success_rate,
                    'true_value': self.sensors[name].state.last_value,
                }
            )
        return result
