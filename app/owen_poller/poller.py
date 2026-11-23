"""Модуль периодического опроса физических устройств."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from serial import SerialException

from app.owen_poller.connection import ConnectionManager
from app.owen_poller.device_registry import DeviceRegistry
from app.owen_poller.exceptions import (
    DeviceAddressAlreadyExists,
    DeviceNameAlreadyExists, DeviceNotFound,
)
from app.owen_poller.sensor import Sensor
from app.owen_poller.storage import SensorConfigStorage

logger = logging.getLogger(__name__)


class SensorsPoller:
    """Главный класс опроса устройств.

    Управляет инициализацией оборудования, сортировкой очереди опроса,
    периодическим сбором данных и сохранением состояния (State).
    """

    def __init__(self, settings):
        self.settings = settings
        self.is_active = False

        use_mock = getattr(settings, 'USE_MOCK_PROVIDER', False)
        self.connection = ConnectionManager(settings.serial_settings, use_mock)
        self.registry = DeviceRegistry()

        storage_path = getattr(
            settings, 'SENSORS_STORAGE_FILE', 'sensors_config.json'
        )
        self.storage = SensorConfigStorage(storage_path)

        initial_configs = self.storage.load_or_init(settings.sensors_settings)
        for s_settings in initial_configs:
            self._create_and_register_sensor(s_settings)

    def _create_and_register_sensor(self, s_settings: dict[str, Any]) -> Sensor:
        """Создать экземпляр Sensor из словаря настроек и добавить в реестр."""
        device_class = s_settings['driver']
        kwargs = {
            k: v
            for k, v in s_settings.items()
            if k not in ('name', 'driver', 'parameter', 'formatter', 'watchdog')
        }

        formatter = s_settings.get('formatter')
        if not formatter:
            raise ValueError(
                f"Отсутствует настройка 'formatter' для сенсора {s_settings['name']}"
            )

        sensor = Sensor(
            name=s_settings['name'],
            device=device_class(**kwargs),
            formatter=formatter,
            provider=self.connection.provider,
            watchdog=s_settings.get('watchdog'),
            parameter=s_settings.get('parameter'),
        )
        self.registry.add_sensor(sensor)
        return sensor

    def register_new_sensor(self, raw_config: dict[str, Any]) -> Sensor:
        """Провалидировать, зарегистрировать новый сенсор и сохранить его локально.

        Args:
            raw_config: Словарь с параметрами нового устройства.

        Returns:
            Созданный экземпляр Sensor.
        """
        name = raw_config['name']
        addr = raw_config['addr']

        if name in self.registry.sensors:
            raise DeviceNameAlreadyExists(name)

        if self.registry.has_address(addr):
            raise DeviceAddressAlreadyExists(addr)

        deserialized_cfg = self.storage.deserialize_item(raw_config)
        sensor = self._create_and_register_sensor(deserialized_cfg)
        self.storage.add_sensor_config(raw_config)

        logger.info(f'Добавлен новый сенсор {name} (адрес {addr}) в список опроса.')
        return sensor

    async def sensors_update(self):
        """Выполнить один проход опроса всех зарегистрированных сенсоров.

        Обновляет runtime-состояние (минутную статистику, количество
        удачных/неудачных чтений).
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
        """Запустить основной бесконечный асинхронный цикл поллера.

        Выполняет опрос и ждет заданное время (POLL_DELAY).
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
        """Остановить цикл поллера."""
        self.is_active = False

    def update_existing_sensor(
            self, target_name: str, raw_config: dict[str, Any]
    ) -> Sensor:
        """Обновить конфигурацию существующего сенсора в реестре и JSON-хранилище.

        Args:
            target_name: Текущее имя обновляемого сенсора.
            raw_config: Словарь с новыми параметрами устройства.

        Returns:
            Обновленный экземпляр Sensor.
        """
        if target_name not in self.registry.sensors:
            raise DeviceNotFound(target_name)

        new_name = raw_config['name']
        new_addr = raw_config['addr']

        if new_name != target_name and new_name in self.registry.sensors:
            raise DeviceNameAlreadyExists(new_name)

        if self.registry.has_address(new_addr, exclude_name=target_name):
            raise DeviceAddressAlreadyExists(new_addr)

        old_sensor = self.registry.sensors[target_name]
        deserialized_cfg = self.storage.deserialize_item(raw_config)

        if new_name != target_name:
            self.registry.remove_sensor(target_name)

        new_sensor = self._create_and_register_sensor(deserialized_cfg)

        # Сохраняем накопленное состояние, если тип драйвера не изменился
        if isinstance(new_sensor.device, old_sensor.device.__class__):
            new_sensor.reading = old_sensor.reading
            new_sensor.state = old_sensor.state

        self.storage.update_sensor_config(target_name, raw_config)
        logger.info(
            f'Сенсор {target_name} обновлен (новое имя: {new_name}, адрес: {new_addr}).'
        )
        return new_sensor

    def delete_existing_sensor(self, target_name: str) -> None:
        """Удалить сенсор из активного опроса и локального JSON-хранилища.

        Args:
            target_name: Имя удаляемого сенсора.
        """
        self.registry.remove_sensor(target_name)
        self.storage.remove_sensor_config(target_name)
        logger.info(f'Сенсор {target_name} удален из списка опроса и хранилища.')
