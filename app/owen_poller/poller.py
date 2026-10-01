import asyncio
import logging
from datetime import datetime

from serial import SerialException

from app.owen_poller.connection import ConnectionManager
from app.owen_poller.device_registry import DeviceRegistry
from app.owen_poller.sensor import Sensor

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

        use_mock = getattr(settings, 'USE_MOCK_PROVIDER', False)
        self.connection = ConnectionManager(settings.serial_settings, use_mock)
        self.registry = DeviceRegistry()

        for s_settings in settings.sensors_settings:
            device_class = s_settings['driver']

            kwargs = {
                k: v
                for k, v in s_settings.items()
                if k not in ('name', 'driver', 'parameter')
            }

            sensor = Sensor(
                name=s_settings['name'],
                device=device_class(**kwargs),
                parameter=s_settings.get('parameter'),
                provider=self.connection.provider,
            )
            self.registry.add_sensor(sensor)

    async def sensors_update(self):
        """
        Выполняет один проход опроса всех зарегистрированных сенсоров.

        Обновляет runtime-состояние (минутную статистику, количество удачных/неудачных чтений).
        """
        port_is_ready = self.connection.connect()
        now = datetime.now()

        for sensor in self.registry.get_sorted_sensors():
            state = sensor.state

            sensor.check_minute_boundary(now)

            if state.last_poll_attempt_ts is not None:
                seconds_since_last_poll = (
                    now - state.last_poll_attempt_ts
                ).total_seconds()
                if seconds_since_last_poll < sensor.device.poll_interval:
                    continue

            state.last_poll_attempt_ts = now

            if not port_is_ready:
                sensor.state.add_fail()
                continue

            try:
                sensor.update()
            except SerialException as e:
                logger.error(f'Обрыв связи во время опроса {sensor.name}: {e}')
                self.connection.disconnect()
                port_is_ready = False

            if port_is_ready:
                await asyncio.sleep(getattr(self.settings, 'INTER_SENSOR_DELAY', 0.15))

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
