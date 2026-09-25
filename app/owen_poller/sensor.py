import logging
from datetime import datetime
from typing import Any

from serial import Serial, SerialException

from app.api.common import SensorReading
from app.api.config import configure_logging
from app.owen_drivers.base_driver import BaseDriver

configure_logging()
logger = logging.getLogger(__name__)


class Sensor:
    """
    Класс-обертка, связывающий физический драйвер (BaseDriver),
    порт связи (Serial) и хранилище результатов (SensorReading).
    Обеспечивает абстракцию "Логического датчика".
    """

    reading: SensorReading

    def __init__(
        self,
        name: str,
        device: BaseDriver,
        parameter: Any,
        serial: Serial,
    ):
        """
        :param name: Логическое имя сенсора в системе.
        :param device: Инициализированный объект драйвера (наследник BaseDriver).
        :param parameter: Параметр для чтения (хеш, регистр и т.д.).
        :param serial: Объект последовательного порта для коммуникации.
        """
        self.name = name
        self.device = device
        self.parameter = parameter
        self.serial = serial
        self.reading = SensorReading()

    def update(self) -> bool:
        """
        Синхронно запрашивает новые данные у драйвера.

        :return: True если опрос прошел успешно, False при ошибках (таймаут, парсинг).
        """
        try:
            self.reading.value = self.device.read_parameter(self.serial, self.parameter)
            self.reading.time = datetime.now()
            return True
        except TimeoutError as err:
            logger.warning(f'Сенсор {self.name}: {err}')
            return False
        except SerialException:
            raise
        except Exception as err:
            logger.warning(f'Ошибка данных сенсора {self.name}: {err}')
            return False

    def get(self) -> dict[str, Any]:
        """Возвращает словарь с текущими сохраненными показаниями."""
        return {
            'name': self.name,
            'reading': self.reading.value,
            'reading_time': self.reading.time,
        }
