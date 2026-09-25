from abc import ABC, abstractmethod
from typing import Any

from serial import Serial


class BaseDriver(ABC):
    """Базовый абстрактный класс для всех драйверов оборудования."""

    # Флаг: True - накопительный счетчик (нужен расчет скорости и diff)
    # False - датчик мгновенных значений
    is_cumulative: bool = False

    # Приоритет в очереди опроса (меньше = опрашивается раньше)
    poll_priority: int = 10

    @abstractmethod
    def read_parameter(self, serial_if: Serial, parameter: Any = None) -> Any:
        """
        Чтение параметра с физического устройства.

        :param serial_if: Открытый порт (Serial)
        :param parameter: Параметр для чтения (хеш, регистр и т.д.)
        :return: Прочитанное значение (int, float, dict и т.д.) или None при ошибке
        """
        pass
