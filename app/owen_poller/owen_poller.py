import asyncio
import copy
import dataclasses
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from serial import Serial

from app import settings
from app.api.common import SensorReading
from app.api.config import configure_logging
from app.owen_counter.owen_ci8 import OwenCI8

from .exeptions import DeviceNotFound

configure_logging()
logger = logging.getLogger(__name__)


@dataclass
class Sensor:
    name: str
    device: OwenCI8
    parameter_hash: bytes
    serial: Serial
    reading: SensorReading = dataclasses.field(default_factory=SensorReading)
    # reading_time: datetime = datetime.now()

    def update(self) -> None:
        try:
            self.reading.value = self.device.read_parameter(
                self.serial, self.parameter_hash)
            self.reading.time = datetime.now()
        except TimeoutError:
            logger.error(f'Сенсор {self.name} не ответил')
        except Exception as err:
            logger.error(f'Сенсор {self.name} {err}')

    def get(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'reading': self.reading.value,
            'reading_time': self.reading.time
        }


class SensorsPoller:

    def __init__(self):
        if settings.serial_settings:
            serial = Serial(**settings.serial_settings)
            serial.close()
            serial.open()
        else:
            serial = None
        self.sensors: dict[str, Sensor] = {}
        for sensor_settings in settings.sensors_settings:
            sensor_name = sensor_settings['name']
            device = sensor_settings['driver']
            self.sensors[sensor_name] = Sensor(
                name=sensor_name,
                device=device(addr=sensor_settings['addr'],
                              addr_len=sensor_settings['addr_len']),
                parameter_hash=sensor_settings['parameter'],
                serial=serial
            )
        self.last_readings = {}

    async def poll(self):
        """
        Цикл опроса устройств.
        """
        while True:
            for sensor in self.sensors.values():
                await asyncio.sleep(0)
                sensor.update()
            await asyncio.sleep(settings.POLL_DELAY)

    def get_sensor_readings(self, sensor_name: str) -> dict[str, Any]:
        try:
            return self.sensors[sensor_name].get()
        except KeyError:
            raise DeviceNotFound(sensor_name)

    def get_list_readings(
            self, work_centers: list[str]
    ) -> list[dict[str, Any]]:
        """
        Запрос данных по списку slug рабочих центров.
        :param work_centers: Список slug рабочих центров.
        :return: Список показаний датчиков.
        """
        for_sent = []
        measured_at = datetime.now()
        for work_center in work_centers:
            response = {
                'sensor': work_center,
                'value': None,
                'measured_at': measured_at,
                'status': 'NOT FOUND'
            }
            if not (sensor := self.sensors.get(work_center)):
                logger.error(f'Device {work_center} not found in settings.py')
                for_sent.append(response)
                continue
            current_reading: SensorReading = sensor.reading
            if current_reading.value is None:
                response['status'] = 'OFFLINE'
                for_sent.append(response)
                continue
            previous_reading: SensorReading = self.last_readings.get(
                sensor.name)
            if previous_reading is None or previous_reading.value is None:
                self.last_readings[sensor.name] = copy.copy(
                    current_reading)
                response['status'] = 'OK'
                for_sent.append(response)
                continue
            duration = current_reading.time - previous_reading.time
            if duration.total_seconds() <= 0:
                continue
            speed = ((current_reading.value - previous_reading.value)
                     / duration.total_seconds()
                     * 60)
            response['value'] = speed
            response['status'] = 'OK'
            for_sent.append(response)
            self.last_readings[sensor.name] = copy.copy(current_reading)
        logger.debug(f'{for_sent=}')
        return for_sent
