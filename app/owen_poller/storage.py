"""Локальное хранилище конфигурации сенсоров в формате JSON."""

import json
import logging
from pathlib import Path
from typing import Any

from app.owen_drivers.base_driver import BaseDriver
from app.owen_drivers.modbus_pvt110 import ModbusPVT110
from app.owen_drivers.owen_ci8 import OwenCI8
from app.owen_drivers.watchdog import FrozenValueWatchdog
from app.owen_poller.formatters import (
    BaseFormatter,
    CounterFormatter,
    EnvironmentFormatter,
)

logger = logging.getLogger(__name__)

DRIVERS_MAP: dict[str, type[BaseDriver]] = {
    'ci8': OwenCI8,
    'owenci8': OwenCI8,
    'pvt110': ModbusPVT110,
    'modbuspvt110': ModbusPVT110,
}

FORMATTERS_MAP: dict[str, type[BaseFormatter]] = {
    'counter': CounterFormatter,
    'counterformatter': CounterFormatter,
    'environment': EnvironmentFormatter,
    'environmentformatter': EnvironmentFormatter,
}

CI8_PARAMS_MAP: dict[str, bytes] = {
    'DCNT': OwenCI8.DCNT,
    'DSPD': OwenCI8.DSPD,
    'DTMR': OwenCI8.DTMR,
}


class SensorConfigStorage:
    """Управляет сохранением и загрузкой конфигурации сенсоров в JSON-файл."""

    def __init__(self, file_path: str | Path = 'sensors_config.json'):
        self.file_path = Path(file_path)

    def load_or_init(
        self, default_settings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Загрузить конфигурацию из файла или инициализировать стартовой.

        Args:
            default_settings: Стартовый список сенсоров из settings.py.

        Returns:
            Список словарей с конфигурацией сенсоров, готовый к инициализации.
        """
        if not self.file_path.exists():
            logger.info(
                'Локальный файл конфигурации не найден. '
                'Инициализация из settings.py...'
            )
            serialized = [self._serialize_item(item) for item in default_settings]
            self._write_file(serialized)
            return [self._deserialize_item(item) for item in serialized]

        logger.info(f'Загрузка конфигурации сенсоров из {self.file_path}')
        raw_data = self._read_file()
        return [self._deserialize_item(item) for item in raw_data]

    def add_sensor_config(self, sensor_cfg: dict[str, Any]) -> None:
        """Добавить новую конфигурацию сенсора в локальный JSON-файл.

        Args:
            sensor_cfg: Словарь с параметрами нового сенсора.
        """
        raw_data = self._read_file() if self.file_path.exists() else []
        raw_data.append(self._serialize_item(sensor_cfg))
        self._write_file(raw_data)

    def get_all_serialized(self) -> list[dict[str, Any]]:
        """Вернуть текущую конфигурацию всех сенсоров в сериализованном виде."""
        if not self.file_path.exists():
            return []
        return self._read_file()

    def _read_file(self) -> list[dict[str, Any]]:
        """Прочитать данные из JSON-файла."""
        with self.file_path.open('r', encoding='utf-8') as file:
            return json.load(file)

    def _write_file(self, data: list[dict[str, Any]]) -> None:
        """Записать данные в JSON-файл."""
        with self.file_path.open('w', encoding='utf-8') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def _serialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Преобразовать Python-объекты настройки сенсора в JSON-совместимый словарь."""
        driver = item['driver']
        driver_name = driver.__name__ if isinstance(driver, type) else str(driver)

        formatter = item.get('formatter')
        if formatter is None:
            formatter_name = (
                'CounterFormatter'
                if driver_name.lower() in ('ci8', 'owenci8')
                else 'EnvironmentFormatter'
            )
        elif isinstance(formatter, type):
            formatter_name = formatter.__name__
        else:
            formatter_name = formatter.__class__.__name__

        param = item.get('parameter')
        if isinstance(param, bytes):
            param_str = f'0x{param.hex()}'
        elif isinstance(param, str) and param.upper() in CI8_PARAMS_MAP:
            param_str = f'0x{CI8_PARAMS_MAP[param.upper()].hex()}'
        else:
            param_str = param

        watchdog = item.get('watchdog')
        watchdog_threshold = (
            watchdog.threshold
            if isinstance(watchdog, FrozenValueWatchdog)
            else item.get('watchdog_threshold')
        )

        res: dict[str, Any] = {
            'name': item['name'],
            'driver': driver_name,
            'addr': item['addr'],
            'formatter': formatter_name,
            'parameter': param_str,
            'watchdog_threshold': watchdog_threshold,
        }
        if 'addr_len' in item and item['addr_len'] is not None:
            res['addr_len'] = item['addr_len']

        return res

    def _deserialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Восстановить Python-объекты из JSON-словаря."""
        driver_key = str(item['driver']).lower()
        driver_cls = DRIVERS_MAP[driver_key]

        fmt_key = str(item['formatter']).lower()
        formatter_obj = FORMATTERS_MAP[fmt_key]()

        param = item.get('parameter')
        if isinstance(param, str):
            if param.startswith('0x'):
                param = bytes.fromhex(param[2:])
            elif param.upper() in CI8_PARAMS_MAP:
                param = CI8_PARAMS_MAP[param.upper()]

        watchdog_threshold = item.get('watchdog_threshold')
        watchdog_obj = (
            FrozenValueWatchdog(threshold=watchdog_threshold)
            if watchdog_threshold
            else None
        )

        res: dict[str, Any] = {
            'name': item['name'],
            'driver': driver_cls,
            'addr': item['addr'],
            'formatter': formatter_obj,
            'parameter': param,
            'watchdog': watchdog_obj,
        }
        if 'addr_len' in item and item['addr_len'] is not None:
            res['addr_len'] = item['addr_len']

        return res
