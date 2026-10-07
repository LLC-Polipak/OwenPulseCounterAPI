import logging
from datetime import datetime
from typing import Any

from serial import SerialException

from app.api.common import SensorReading
from app.api.config import configure_logging
from app.owen_drivers.base_driver import BaseDriver
from app.owen_drivers.watchdog import FrozenValueWatchdog
from app.owen_poller.formatters import BaseFormatter
from app.owen_poller.state import SensorRuntimeState
from app.providers.base_provider import BaseDataProvider

configure_logging()
logger = logging.getLogger(__name__)


class Sensor:
    """
    Класс-обертка, связывающий физический драйвер (BaseDriver),
    порт связи (Serial) и хранилище результатов (SensorReading).
    Обеспечивает абстракцию "Логического датчика".
    """

    def __init__(
        self,
        name: str,
        device: BaseDriver,
        provider: BaseDataProvider,
        formatter: BaseFormatter,
        watchdog: FrozenValueWatchdog | None = None,
        parameter: Any = None,
    ):
        """
        :param name: Логическое имя сенсора в системе.
        :param device: Инициализированный объект драйвера (наследник BaseDriver).
        :param parameter: Параметр для чтения (хеш, регистр и т.д.).
        :param provider: Поставщик данных.
        :param formatter: Форматтер данных.
        :param watchdog: Наблюдатель за заморозкой значений приборов.
        """
        self.name = name
        self.device = device
        self.parameter = parameter
        self.provider = provider
        self.formatter = formatter
        self.watchdog = watchdog
        self.reading = SensorReading()
        self.state = SensorRuntimeState()

    def check_minute_boundary(self, now: datetime) -> None:
        """Проверяет смену минуты и дает команду на формирование минутного снимка."""
        self.state.check_minute_boundary(now, self.device)

    def update(self) -> bool:
        """
        Выполняет физический запрос к оборудованию.
        При успешном ответе обновляет значения начала и конца минуты в state.

        :return: True если опрос прошел успешно, False при логических ошибках.
        """
        try:
            val = self.device.read_parameter(self.provider, parametr=self.parameter)

            if self.watchdog and self.watchdog.feed(val):
                logger.error(f'Сенсор {self.name}: Данные заморожены! Инициирую сброс.')
                self.device.reboot(self.provider)
                self.state.add_fail()
                return False

            self.reading.value = val
            self.reading.time = datetime.now()

            self.state.add_success(val, self.reading.time)

            return True

        except TimeoutError:
            logger.warning(f'Сенсор {self.name} не ответил (таймаут)')
            self.state.add_fail()
            return False
        except SerialException:
            self.state.add_fail()
            raise
        except Exception as err:
            logger.warning(f'Ошибка данных сенсора {self.name}: {err}')
            self.state.add_fail()
            return False

    def get(self) -> dict[str, Any]:
        """Возвращает словарь с текущими сохраненными показаниями."""
        return {
            'name': self.name,
            'reading': self.reading.value,
            'reading_time': self.reading.time,
        }
