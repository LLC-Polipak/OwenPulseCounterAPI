"""Базовый абстрактный класс для драйверов оборудования."""

from abc import ABC, abstractmethod
from typing import Any

from app.owen_poller.enums import SensorStatus
from app.owen_poller.state import SensorRuntimeState
from app.providers.base_provider import BaseDataProvider


class BaseDriver(ABC):
    """Абстрактный интерфейс для любого драйвера оборудования.

    Задает контракт на чтение данных и расчет метрик.
    """

    # Приоритет в очереди опроса (меньше = опрашивается раньше)
    poll_priority: int = 10
    # Минимальное время между опросами этого прибора (в секундах)
    poll_interval: float = 1.0

    # Минимально допустимая доля успешных запросов за минуту (от 0.0 до 1.0)
    min_success_rate: float = 0.5

    def __init__(self, addr: int, **kwargs):
        self.addr = addr

    def calculate_success_rate(self, attempt_count: int, success_count: int) -> float:
        """Вычислить процент успешных запросов.

        Метод может быть переопределен, если прибору нужна иная математика расчета.
        """
        if attempt_count == 0:
            return 0.0
        return round(success_count / attempt_count, 3)

    @abstractmethod
    def read_parameter(self, provider: BaseDataProvider, **kwargs) -> Any:
        """Прочитать параметр с физического устройства.

        Args:
            provider: Поставщик данных.
            **kwargs: Любые дополнительные параметры.

        Returns:
            Прочитанное значение (int, float, dict и т.д.) или None при ошибке.
        """

    @abstractmethod
    def calculate_minute_metric(self, start_val: Any, end_val: Any) -> Any:
        """Рассчитать итоговую метрику за прошедшую завершенную минуту.

        Используется для формирования исторического Snapshot'а.

        Args:
            start_val: Значение датчика в начале минуты.
            end_val: Значение датчика в конце минуты.

        Returns:
            Итоговое вычисленное значение (например, разница для счетчиков).
        """

    @abstractmethod
    def calculate_instant_metric(
        self, curr_val: Any, prev_val: Any, duration_sec: float
    ) -> Any:
        """Рассчитать метрику в реальном времени.

        Args:
            curr_val: Текущее значение.
            prev_val: Значение с момента прошлого запроса.
            duration_sec: Время в секундах между текущим и прошлым запросом.

        Returns:
            Мгновенная скорость или текущее значение.
        """

    @abstractmethod
    def get_status(self, metric: Any, state: SensorRuntimeState) -> SensorStatus:
        """Определить логическое состояние прибора.

        Анализирует вычисленную метрику и runtime-статистику прибора.

        Args:
            metric: Вычисленная метрика (скорость, дельта, словари с градусами).
            state: Текущее состояние (кол-во ошибок, время последнего успешного ответа).

        Returns:
            Статус прибора (OK, STOP, OFFLINE, UNKNOWN).
        """

    @abstractmethod
    def reboot(self, provider: BaseDataProvider) -> bool:
        """Отправить команду на программную перезагрузку физического устройства.

        Args:
            provider: Провайдер связи (COM-порт / Mock).

        Returns:
            True, если команда успешно принята устройством. По умолчанию False.
        """

    @abstractmethod
    def read_device_status(self, provider: BaseDataProvider) -> dict[str, Any] | None:
        """Считать аппаратный статус или код ошибки с самого устройства.

        Args:
            provider: Провайдер связи (COM-порт / Mock).

        Returns:
            Словарь с описанием статуса, либо None, если не поддерживается.
        """
