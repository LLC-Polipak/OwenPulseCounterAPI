import asyncio
import copy
import logging
from datetime import datetime
from typing import Any

from serial import Serial, SerialException

from app.api.common import SensorReading
from app.api.config import configure_logging
from app.owen_drivers.owen_ci8 import OwenCI8

from .exeptions import DeviceNotFound
from .sensor import Sensor
from .state import SensorRuntimeState
from .utils import finalize_previous_minute, start_new_minute

configure_logging()
logger = logging.getLogger(__name__)


class SensorsPoller:
    """
    Главный класс опроса устройств.

    Управляет инициализацией оборудования, сортировкой очереди опроса,
    периодическим сбором данных и сохранением состояния (State).
    """

    def __init__(self, settings):
        """
        Инициализирует поллер на основе файла конфигурации.

        :param settings: Объект настроек, содержащий параметры порта и список сенсоров.
        """
        self.settings = settings
        self.is_active = False
        self.serial = None

        self._connect_serial()

        self.sensors: dict[str, Sensor] = {}
        for sensor_settings in settings.sensors_settings:
            self.sensors[sensor_settings.get('name')] = self._create_sensor(
                sensor_settings
            )

        self._sort_sensors()

        self.state: dict[str, SensorRuntimeState] = {
            name: SensorRuntimeState() for name in self.sensors
        }
        self.last_readings = {}

    async def sensors_update(self):
        """
        Выполняет один проход опроса всех зарегистрированных сенсоров.

        Обновляет runtime-состояние (минутную статистику, количество удачных/неудачных чтений).
        """
        port_is_ready = self._connect_serial()

        now = datetime.now()
        minute = now.replace(second=0, microsecond=0)

        for sensor in self.sensors.values():
            state = self.state[sensor.name]

            if state.current_minute != minute:
                if state.current_minute is not None:
                    finalize_previous_minute(state, sensor)
                start_new_minute(state, minute)

            state.attempt_count += 1

            if not port_is_ready:
                continue

            try:
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()

                if sensor.update():
                    state.success_count += 1

                reading = sensor.reading

                if reading.value is not None:
                    state.last_success_ts = reading.time
                    if state.minute_start_value is None:
                        state.minute_start_value = reading.value
                    state.minute_end_value = reading.value
                    state.last_value = reading.value
                    state.last_ts = reading.time

            except SerialException as e:
                logger.error(f'Обрыв связи во время опроса {sensor.name}: {e}')
                self.serial.close()
                port_is_ready = False

            if port_is_ready:
                inter_delay = getattr(self.settings, 'INTER_SENSOR_DELAY', 0.15)
                await asyncio.sleep(inter_delay)

    async def poll(self):
        """
        Основной бесконечный асинхронный цикл поллера.

        Запускает опрос и ждет заданное время (POLL_DELAY).
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
        """Останавливает цикл поллера."""
        self.is_active = False

    def get_sensor_readings(self, sensor_name: str) -> dict[str, Any]:
        """
        Возвращает "сырые" данные конкретного сенсора.

        :param sensor_name: Имя сенсора.
        :raises DeviceNotFound: Если сенсор с таким именем не зарегистрирован.
        """
        try:
            return self.sensors[sensor_name].get()
        except KeyError:
            raise DeviceNotFound(sensor_name) from None

    def get_list_readings(self, work_centers: list[str]) -> list[dict[str, Any]]:
        """
        Формирует список мгновенных показаний (или вычисленной скорости)
        для внешних запросов.

        :param work_centers: Список имен сенсоров для формирования ответа.
        :return: Список словарей со статусами и значениями.
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

            if not sensor.device.is_cumulative:
                response['value'] = current_reading.value
                response['status'] = 'OK'
                for_sent.append(response)
                self.last_readings[sensor.name] = copy.copy(current_reading)
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
        """
        Формирует отчет о состоянии сенсоров за последнюю завершенную минуту.

        :param sensors: Список имен сенсоров для отчета.
        :return: Список словарей с метриками (успешность опроса, статусы).
        """
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

            result.append(
                {
                    'sensor': name,
                    'status': snapshot.status,
                    'value': snapshot.value,
                    'measured_at': snapshot.minute,
                    'changed_at': snapshot.last_seen_at,
                    'success_rate': snapshot.success_rate,
                    'true_value': state.last_value,
                }
            )

        logger.debug(f'get_minute_state={result}')
        return result

    def test_sensor_by_addr(self, addr: int) -> Sensor:
        """Создает тестовый инстанс сенсора СИ8 по указанному адресу."""
        return self._create_sensor(
            {
                'name': 'test',
                'driver': OwenCI8,
                'addr': addr,
                'addr_len': 8,
                'parameter': OwenCI8.DCNT,
            }
        )

    def _create_sensor(self, sensor_settings: dict[str, Any]) -> Sensor:
        """
        Фабричный метод для создания экземпляра логического сенсора.

        :param sensor_settings: Словарь конфигурации одного сенсора из settings.py.
        :return: Инициализированный объект Sensor.
        """
        sensor_name = sensor_settings['name']
        device_class = sensor_settings['driver']
        return Sensor(
            name=sensor_name,
            device=device_class(
                addr=sensor_settings['addr'],
                addr_len=sensor_settings.get('addr_len', 8),
            ),
            parameter=sensor_settings.get('parameter'),
            serial=self.serial,
        )

    def _sort_sensors(self):
        """
        Сортирует словарь сенсоров на основе приоритета драйвера (poll_priority).

        Гарантирует, что более чувствительные протоколы опрашиваются первыми.
        """
        sorted_items = sorted(
            self.sensors.items(), key=lambda item: item[1].device.poll_priority
        )
        self.sensors = dict(sorted_items)

    def _connect_serial(self) -> bool:
        """
        Инициализирует и безопасно открывает COM-порт.
        Возвращает True, если порт готов к работе, и False, если недоступен.
        """
        if not self.settings.serial_settings:
            return False

        if self.serial is None:
            kwargs = self.settings.serial_settings.copy()
            self.serial = Serial(**kwargs)

        if self.serial.is_open:
            return True

        try:
            logger.info(f'Попытка подключения к порту {self.serial.port}...')
            self.serial.open()
            logger.info('Соединение с портом успешно установлено!')
            return True
        except SerialException as e:
            logger.error(f'COM-порт недоступен: {e}')
            return False
