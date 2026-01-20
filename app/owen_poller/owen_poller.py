import asyncio
import copy
import logging
from datetime import datetime
from typing import Any

from serial import Serial

from app.api.common import SensorReading, SensorRuntimeState
from app.api.config import configure_logging
from app.owen_counter.owen_ci8 import OwenCI8

from .exeptions import DeviceNotFound
from .sensor import Sensor

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
            print(sensor_settings)
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
        for sensor in self.sensors.values():
            sensor.update()
            state = self.state[sensor.name]

            reading = sensor.reading
            if reading.value is None:
                await asyncio.sleep(0)
                continue

            # --- availability ---
            state.last_success_ts = reading.time

            # --- diff ---
            if state.last_value is not None:
                if reading.value < state.last_value:
                    diff = sensor.device.MAX_VALUE - state.last_value + reading.value
                else:
                    diff = reading.value - state.last_value
            else:
                diff = 0

            # --- minute aggregation ---
            minute = reading.time.replace(second=0, microsecond=0)
            if state.current_minute != minute:
                state.last_minute_total = state.current_minute_total
                state.last_minute_ts = state.current_minute
                state.current_minute_total = 0
                state.current_minute = minute

            state.current_minute_total += diff

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
        now = datetime.now()
        result = []

        for name in sensors:
            if name not in self.sensors:
                result.append(
                    {
                        'sensor': name,
                        'measured_at': None,
                        'value': None,
                        'status': 'NOT_FOUND',
                        'true_value': None,
                    }
                )
                continue

            state = self.state.get(name)
            if not state:
                continue

            if (
                not state.last_success_ts
                or not state.last_minute_ts
                or (now - state.last_success_ts).total_seconds() > 60
            ):
                status = 'UNKNOWN'
            elif state.last_minute_total == 0:
                status = 'STOP'
            else:
                status = 'OK'

            result.append(
                {
                    'sensor': name,
                    'measured_at': state.last_minute_ts,
                    'value': state.last_minute_total,
                    'status': status,
                    'true_value': state.last_value,
                }
            )

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
