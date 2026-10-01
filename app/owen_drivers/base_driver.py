from abc import ABC, abstractmethod
from typing import Any

from app.owen_poller.enums import SensorStatus
from app.owen_poller.state import SensorRuntimeState
from app.providers.base_provider import BaseDataProvider


class BaseDriver(ABC):
    """
    Абстрактный интерфейс для любого драйвера оборудования.
    Задает контракт на чтение данных и расчет метрик.
    """

    # Приоритет в очереди опроса (меньше = опрашивается раньше)
    poll_priority: int = 10
    # Минимальное время между опросами этого прибора (в секундах)
    poll_interval: float = 1.0

    # Минимально допустимая доля успешных запросов за минуту (от 0.0 до 1.0)
    min_success_rate: float = 0.5

    def __init__(self, addr: int, **kwargs):
        """
        :param addr: Адрес устройства.
        :param kwargs: Любые дополнительные параметры (например, addr_len).
        """
        self.addr = addr

    def calculate_success_rate(self, attempt_count: int, success_count: int) -> float:
        """
        Самостоятельно вычисляет процент успешных запросов.

        Метод может быть переопределен, если прибору нужна иная математика расчета.
        """
        if attempt_count == 0:
            return 0.0
        return round(success_count / attempt_count, 3)

    @abstractmethod
    def read_parameter(self, provider: BaseDataProvider, **kwargs) -> Any:
        """
        Чтение параметра с физического устройства.

        :param provider: Поставщик данных.
        :param kwargs: Любые дополнительные параметры.
        :return: Прочитанное значение (int, float, dict и т.д.) или None при ошибке
        """
        pass

    @abstractmethod
    def calculate_minute_metric(self, start_val: Any, end_val: Any) -> Any:
        """
        Рассчитывает итоговую метрику за прошедшую завершенную минуту.
        Используется для формирования исторического Snapshot'а.

        :param start_val: Значение датчика в начале минуты.
        :param end_val: Значение датчика в конце минуты.
        :return: Итоговое вычисленное значение (например, разница для счетчиков).
        """
        pass

    @abstractmethod
    def calculate_instant_metric(
        self, curr_val: Any, prev_val: Any, duration_sec: float
    ) -> Any:
        """
        Рассчитывает метрику в реальном времени.

        :param curr_val: Текущее значение.
        :param prev_val: Значение с момента прошлого запроса.
        :param duration_sec: Время в секундах между текущим и прошлым запросом.
        :return: Мгновенная скорость или текущее значение.
        """
        pass

    @abstractmethod
    def get_status(self, metric: Any, state: SensorRuntimeState) -> SensorStatus:
        """
        Анализирует вычисленную метрику и runtime-статистику прибора
        для определения его логического состояния.

        :param metric: Вычисленная метрика (скорость, дельта, словари с градусами).
        :param state: Текущее состояние (кол-во ошибок, время последнего успешного ответа).
        :return: Статус прибора (OK, STOP, OFFLINE, UNKNOWN).
        """
        pass
