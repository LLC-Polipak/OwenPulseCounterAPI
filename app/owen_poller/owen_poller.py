import asyncio
import copy
import logging
from datetime import datetime
from typing import Any

from serial import Serial

from app.api.common import SensorReading
from app.api.config import configure_logging
from app.owen_counter.owen_ci8 import OwenCI8

from .exeptions import DeviceNotFound
from .sensor import Sensor
from .state import SensorRuntimeState
from .utils import finalize_previous_minute, start_new_minute

configure_logging()
logger = logging.getLogger(__name__)


class SensorsPoller:
    def __init__(self, settings):
        self.settings = settings
        self.is_active = False
        if settings.serial_settings:
            self.serial = Serial(**settings.serial_settings)
            self.serial.close()
            self.serial.open()
        else:
            self.serial = None
        self.sensors: dict[str, Sensor] = {}
        for sensor_settings in settings.sensors_settings:
            self.sensors[sensor_settings.get('name')] = self._create_sensor(
                sensor_settings
            )

        self.state: dict[str, SensorRuntimeState] = {
            name: SensorRuntimeState() for name in self.sensors
        }
        self.last_readings = {}

    def _create_sensor(self, sensor_settings: dict[str, Any]) -> Sensor:
        sensor_name = sensor_settings['name']
        device = sensor_settings['driver']
        return Sensor(
            name=sensor_name,
            device=device(
                addr=sensor_settings['addr'], addr_len=sensor_settings['addr_len']
            ),
            parameter_hash=sensor_settings['parameter'],
            serial=self.serial,
        )

    async def sensors_update(self):
        now = datetime.now()
        minute = now.replace(second=0, microsecond=0)

        for sensor in self.sensors.values():
            state = self.state[sensor.name]

            if state.current_minute != minute:
                if state.current_minute is not None:
                    finalize_previous_minute(state, sensor)
                start_new_minute(state, minute)

            state.attempt_count += 1
            if sensor.update():
                state.success_count += 1
            reading = sensor.reading

            if reading.value is None:
                continue

            state.last_success_ts = reading.time

            if state.minute_start_value is None:
                state.minute_start_value = reading.value

            state.minute_end_value = reading.value
            state.last_value = reading.value
            state.last_ts = reading.time
            await asyncio.sleep(0)

    async def poll(self):
        """
        Цикл опроса устройств.
        """
        self.is_active = True
        try:
            while self.is_active:
                await self.sensors_update()
                await asyncio.sleep(self.settings.POLL_DELAY)
        except asyncio.CancelledError:
            logger.info('Poller cancelled')
            self.is_active = False
            raise

    def stop(self):
        self.is_active = False

    def get_sensor_readings(self, sensor_name: str) -> dict[str, Any]:
        try:
            return self.sensors[sensor_name].get()
        except KeyError:
            raise DeviceNotFound(sensor_name) from None

    def get_list_readings(self, work_centers: list[str]) -> list[dict[str, Any]]:
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
                'status': 'NOT FOUND',
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
            previous_reading: SensorReading = self.last_readings.get(sensor.name)
            if previous_reading is None or previous_reading.value is None:
                self.last_readings[sensor.name] = copy.copy(current_reading)
                response['status'] = 'OK'
                for_sent.append(response)
                continue
            duration = current_reading.time - previous_reading.time
            if duration.total_seconds() <= 0:
                continue
            if current_reading.value < previous_reading.value:
                value_diff = (
                    sensor.device.MAX_VALUE
                    - previous_reading.value
                    + current_reading.value
                )
            else:
                value_diff = current_reading.value - previous_reading.value

            speed = value_diff / duration.total_seconds() * 60

            response['value'] = speed
            response['status'] = 'OK'
            for_sent.append(response)
            self.last_readings[sensor.name] = copy.copy(current_reading)
        logger.debug(f'{for_sent=}')
        return for_sent

    def get_minute_state(self, sensors: list[str]) -> list[dict]:
        result = []

        for name in sensors:
            if name not in self.sensors:
                result.append(
                    {
                        'sensor': name,
                        'status': 'NOT_FOUND',
                        'value': None,
                        'measured_at': None,
                        'changed_at': None,
                        'success_rate': 0.0,
                    }
                )
                continue

            state = self.state[name]
            snapshot = state.last_minute_snapshot

            if not snapshot or snapshot.minute is None:
                continue

            status = snapshot.status

            result.append(
                {
                    'sensor': name,
                    'status': status,
                    'value': snapshot.value,
                    'measured_at': snapshot.minute,
                    'changed_at': snapshot.last_seen_at,
                    'success_rate': snapshot.success_rate,
                    'true_value': state.last_value,
                }
            )

        logger.error(f'get_minute_state={result}')

        return result

    def test_sensor_by_addr(self, addr: int) -> Sensor:
        return self._create_sensor(
            {
                'name': 'test',
                'driver': OwenCI8,
                'addr': addr,
                'addr_len': 8,
                'parameter': OwenCI8.DCNT,
            }
        )
